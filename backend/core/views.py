import mimetypes

from django.db import connection, transaction
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    AuditLog,
    Detection,
    Finding,
    Frame,
    InferenceRun,
    Mission,
    MissionMember,
    ModelVersion,
    Review,
)
from .serializers import (
    AuditLogSerializer,
    DetectionSerializer,
    FindingSerializer,
    FindingYazSerializer,
    MissionMemberRolSerializer,
    MissionMemberSerializer,
    MissionMemberYazSerializer,
    ReviewSerializer,
    ReviewYazSerializer,
    FrameSerializer,
    InferenceRunSerializer,
    MissionSerializer,
    ModelVersionSerializer,
    RunCreateSerializer,
)
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point

from .denetim import denetim_yaz
from .kumeleme import VARSAYILAN_ESIK_METRE, gorevi_kumele, kume_ozeti
from .services import InvalidImageError, ingest_frame
from .tasks import run_inference
from .yetki import gorevi_al_veya_404, kullanicinin_gorevleri, uyelik_getir


def _nokta_yap(enlem, boylam):
    """Enlem/boylamdan Point uretir. Ikisi de yoksa None -- "0,0" DEGIL."""
    if enlem is None or boylam is None:
        return None
    # Point(x, y) = Point(boylam, enlem). Sira burada tek yerde belirleniyor.
    return Point(float(boylam), float(enlem), srid=4326)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Uygulama ve veritabani durumu. Kimlik dogrulama gerektirmez."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return Response(
            {"status": "degraded", "database": "error", "detail": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"status": "ok", "database": "ok"})


def gorev_querysetini_kur(user):
    """Kullanicinin gorevleri; kare sayimlari ve kosulari onceden yuklenmis.

    Sayimlar tek sorguda annotate edilir ve kosular prefetch edilir: gorev
    sayisi arttikca sorgu sayisi artmasin (N+1 yok).
    """
    # Erisim artik created_by'a DEGIL uyelige bakiyor (core/yetki.py).
    sayim_annotasyonlari = {
        f"frames_{durum}_annotated": Count(
            "frames", filter=Q(frames__status=durum), distinct=True
        )
        for durum in Frame.Status.values
    }
    return (
        kullanicinin_gorevleri(user)
        .annotate(frame_count_annotated=Count("frames", distinct=True))
        .annotate(**sayim_annotasyonlari)
        .prefetch_related(
            Prefetch(
                "runs",
                queryset=InferenceRun.objects.select_related("model_version").order_by(
                    "-started_at", "-id"
                ),
                to_attr="son_kosular",
            )
        )
    )


class MissionListCreateView(generics.ListCreateAPIView):
    serializer_class = MissionSerializer

    def get_queryset(self):
        # Kullanici yalnizca kendi olusturdugu gorevleri gorur.
        return gorev_querysetini_kur(self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        # Owner uyeligini models.py'deki post_save sinyali olusturuyor; burada
        # ikinci kez yazmak gereksiz ve iki yerde tutulan bir kural demek olurdu.
        serializer.save(created_by=self.request.user)


class MissionDetailView(generics.RetrieveAPIView):
    """GET /api/missions/{id}/ -- tek gorev.

    Arayuz gorev ayrintisina dogrudan gidildiginde (yeniden yukleme, yer imi)
    gorevi listeden suzmek zorunda kalmasin diye var. Sahiplik queryset'te
    suzuluyor: baskasinin gorevi 404.
    """

    serializer_class = MissionSerializer

    def get_queryset(self):
        return gorev_querysetini_kur(self.request.user)


class MissionFrameListCreateView(generics.ListAPIView):
    serializer_class = FrameSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_mission(self, *, yazma=False):
        return gorevi_al_veya_404(
            self.request.user, self.kwargs["mission_id"], yazma=yazma
        )

    def get_queryset(self):
        queryset = Frame.objects.filter(mission=self.get_mission()).order_by("-created_at")
        wanted = self.request.query_params.get("status")
        if wanted:
            if wanted not in Frame.Status.values:
                raise ValidationError({"status": f"Gecersiz durum: {wanted}"})
            queryset = queryset.filter(status=wanted)
        return queryset

    def post(self, request, *args, **kwargs):
        # Kare eklemek yazma yetkisi ister; viewer ekleyemez.
        mission = self.get_mission(yazma=True)
        files = request.FILES.getlist("images")
        if not files:
            raise ValidationError({"images": "En az bir dosya gonderilmeli."})

        results = []
        for uploaded in files:
            try:
                frame, duplicate = ingest_frame(mission, uploaded)
            except InvalidImageError as exc:
                raise ValidationError({"images": f"{uploaded.name}: {exc}"})
            results.append(
                {
                    "id": frame.id,
                    "filename": frame.original_filename,
                    "duplicate": duplicate,
                    "width": frame.width,
                    "height": frame.height,
                }
            )
        return Response(results, status=status.HTTP_201_CREATED)


class ModelVersionListView(generics.ListAPIView):
    """Kullanilabilir model surumleri. Kimlik dogrulama ister."""

    serializer_class = ModelVersionSerializer
    queryset = ModelVersion.objects.all().order_by("-created_at")


class MissionRunListCreateView(generics.ListAPIView):
    """GET  /api/missions/{id}/runs/ -- gorevin kosulari, yeniden eskiye.
    POST /api/missions/{id}/runs/ -- taramayi baslatir.

    Listeleme, arayuz sayfayi yeniden yukledikten sonra gorevin son/aktif
    kosusunu bulabilsin diye eklendi; run_id'yi istemcide saklamak yeniden
    yuklemede kaybolur.
    """

    def get_serializer_class(self):
        if self.request.method == "POST":
            return RunCreateSerializer
        return InferenceRunSerializer

    def get_queryset(self):
        mission = gorevi_al_veya_404(self.request.user, self.kwargs["mission_id"])
        return (
            InferenceRun.objects.filter(mission=mission)
            .select_related("model_version")
            .order_by("-started_at", "-id")
        )

    def post(self, request, mission_id):
        # Uye olmayan 404, salt okunur uye 403 alir (core/yetki.py).
        mission = gorevi_al_veya_404(request.user, mission_id, yazma=True)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not Frame.objects.filter(mission=mission).exists():
            raise ValidationError({"frames": "Gorevde hic kare yok, tarama baslatilamaz."})

        run = InferenceRun.objects.create(
            mission=mission,
            model_version=data["model_version"],
            conf_threshold=data["conf_threshold"],
            iou_threshold=data["iou_threshold"],
            tile_size=data["tile_size"],
            overlap_ratio=data["overlap_ratio"],
            status=InferenceRun.Status.PENDING,
            frames_total=Frame.objects.filter(mission=mission).count(),
        )

        # Gorev, kayit COMMIT olduktan SONRA kuyruga girsin: aksi halde isci
        # henuz yazilmamis bir run_id'yi okumaya calisip DoesNotExist alir.
        transaction.on_commit(lambda: run_inference.delay(run.id))

        return Response(
            {"run_id": run.id, "status": run.status, "frames_total": run.frames_total},
            status=status.HTTP_202_ACCEPTED,
        )


class RunDetailView(generics.RetrieveAPIView):
    """GET /api/runs/{id}/ -- durum ve ilerleme."""

    serializer_class = InferenceRunSerializer

    def get_queryset(self):
        return InferenceRun.objects.filter(
            mission__members__user=self.request.user
        ).select_related("model_version")


class RunDetectionListView(generics.ListAPIView):
    """GET /api/runs/{id}/detections/ -- skora gore azalan, sayfali.

    Guven esigi KAYDA PISIRILMEZ; burada, okuma aninda uygulanir. Varsayilan
    olarak kosunun kendi conf_threshold'u kullanilir, min_score verilirse o
    kullanilir. Boylece tek bir pahali taramadan her esik icin sonuc alinabilir.
    """

    serializer_class = DetectionSerializer

    def get_run(self):
        return get_object_or_404(
            InferenceRun,
            pk=self.kwargs["run_id"],
            mission__members__user=self.request.user,
        )

    def get_queryset(self):
        run = self.get_run()
        queryset = Detection.objects.filter(inference_run=run)

        raw_min_score = self.request.query_params.get("min_score")
        if raw_min_score is None:
            esik = run.conf_threshold
        else:
            try:
                esik = float(raw_min_score)
            except ValueError:
                raise ValidationError({"min_score": f"Sayi bekleniyor: {raw_min_score}"})
            if not 0.0 <= esik <= 1.0:
                raise ValidationError({"min_score": "[0, 1] araliginda olmali."})
        queryset = queryset.filter(score__gte=esik)

        raw_frame_id = self.request.query_params.get("frame_id")
        if raw_frame_id is not None:
            try:
                frame_id = int(raw_frame_id)
            except ValueError:
                raise ValidationError({"frame_id": f"Tam sayi bekleniyor: {raw_frame_id}"})
            queryset = queryset.filter(frame_id=frame_id)

        # Skora gore azalan; esitlikte id ile kararli sirala ki sayfalama
        # sinirinda kayit tekrarlanmasin veya atlanmasin.
        return queryset.order_by("-score", "id")


class FrameImageView(generics.GenericAPIView):
    """GET /api/frames/{id}/image/ -- kareyi kimlik dogrulamasiyla verir.

    Neden var: FrameSerializer.image alani MEDIA_URL altinda bir adres uretir,
    ama o adres yalnizca DEBUG acikken ve KIMLIK DOGRULAMASIZ servis edilir --
    adresi bilen herkes goruntuyu indirir. Operator arayuzunun goruntuye
    erismesi icin token'i URL'ye koymak da cozum degil: adres gecmiste, log'da
    ve Referer basliginda kalir. Bu uc, token'i Authorization basliginda alir.

    Dosya yolu ISTEMCIDEN GELMEZ: yalnizca Frame birincil anahtari alinir,
    dosya adi veritabanindaki kayittan okunur. Boylece yol gecisi (path
    traversal) yuzeyi yoktur. Sahiplik queryset'te suzulur: baskasinin karesi
    404 doner.
    """

    # Sema ureticileri serializer bekler; bu uc ikili veri dondurur.
    serializer_class = None

    def get(self, request, frame_id):
        # Uyelik disindaki kullanici icin 404: karenin varligi bile sizmaz.
        frame = get_object_or_404(
            Frame, pk=frame_id, mission__members__user=request.user
        )
        try:
            dosya = frame.image.open("rb")
        except (FileNotFoundError, ValueError):
            raise Http404("Kare dosyasi bulunamadi.")

        # Icerik turu KAYITLI dosya adindan tahmin edilir; tahmin edilemezse
        # tarayici turu kendisi tahmin etmesin diye genel ikili tur verilir.
        tur, _ = mimetypes.guess_type(frame.image.name)
        if tur is None or not tur.startswith("image/"):
            tur = "application/octet-stream"

        yanit = FileResponse(dosya, content_type=tur)
        yanit["Content-Disposition"] = "inline"
        yanit["X-Content-Type-Options"] = "nosniff"
        return yanit


# =========================================================================
# Hafta 6: uyelik, inceleme, bulgu, kumeleme ve denetim uclari
# =========================================================================


class MissionMemberListCreateView(generics.ListAPIView):
    """GET  /api/missions/{id}/members/  -- uyeler (her uye gorebilir)
    POST /api/missions/{id}/members/  -- uye ekle (yalnizca owner)
    """

    serializer_class = MissionMemberSerializer

    def get_queryset(self):
        mission = gorevi_al_veya_404(self.request.user, self.kwargs["mission_id"])
        return (
            MissionMember.objects.filter(mission=mission)
            .select_related("user")
            .order_by("role", "user__username")
        )

    def post(self, request, mission_id):
        mission = gorevi_al_veya_404(request.user, mission_id, yonetim=True)
        serializer = MissionMemberYazSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        veri = serializer.validated_data

        kullanici = User.objects.filter(username=veri["username"]).first()
        if kullanici is None:
            raise ValidationError({"username": "Boyle bir kullanici yok."})
        if MissionMember.objects.filter(mission=mission, user=kullanici).exists():
            raise ValidationError({"username": "Bu kullanici zaten gorevde uye."})

        with transaction.atomic():
            uyelik = MissionMember.objects.create(
                mission=mission, user=kullanici, role=veri["role"], added_by=request.user
            )
            denetim_yaz(
                actor=request.user, mission=mission,
                action=AuditLog.Action.MEMBER_ADDED, nesne=uyelik,
                sonraki={"username": kullanici.username, "role": uyelik.role},
            )
        return Response(
            MissionMemberSerializer(uyelik).data, status=status.HTTP_201_CREATED
        )


class MissionMemberDetailView(generics.GenericAPIView):
    """PATCH/DELETE /api/missions/{id}/members/{member_id}/ -- yalnizca owner."""

    serializer_class = MissionMemberRolSerializer

    def _uyeligi_al(self, request, mission_id, member_id):
        mission = gorevi_al_veya_404(request.user, mission_id, yonetim=True)
        uyelik = get_object_or_404(MissionMember, pk=member_id, mission=mission)
        return mission, uyelik

    def _son_owner_mi(self, mission, uyelik):
        if uyelik.role != MissionMember.Role.OWNER:
            return False
        return (
            MissionMember.objects.filter(
                mission=mission, role=MissionMember.Role.OWNER
            ).count()
            <= 1
        )

    def patch(self, request, mission_id, member_id):
        mission, uyelik = self._uyeligi_al(request, mission_id, member_id)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        yeni_rol = serializer.validated_data["role"]

        # Son owner'in rolu dusurulemez: gorev sahipsiz kalirsa uyelik ve rol
        # yonetimi bir daha hic yapilamaz.
        if self._son_owner_mi(mission, uyelik) and yeni_rol != MissionMember.Role.OWNER:
            raise ValidationError(
                {"role": "Gorevin son sahibi baska bir role dusurulemez."}
            )

        eski_rol = uyelik.role
        if eski_rol == yeni_rol:
            return Response(MissionMemberSerializer(uyelik).data)

        with transaction.atomic():
            uyelik.role = yeni_rol
            uyelik.save(update_fields=["role", "updated_at"])
            denetim_yaz(
                actor=request.user, mission=mission,
                action=AuditLog.Action.MEMBER_ROLE_CHANGED, nesne=uyelik,
                onceki={"role": eski_rol}, sonraki={"role": yeni_rol},
                ek={"username": uyelik.user.username},
            )
        return Response(MissionMemberSerializer(uyelik).data)

    def delete(self, request, mission_id, member_id):
        mission, uyelik = self._uyeligi_al(request, mission_id, member_id)
        if self._son_owner_mi(mission, uyelik):
            raise ValidationError(
                {"member": "Gorevin son sahibi cikarilamaz."}
            )

        with transaction.atomic():
            kullanici_adi = uyelik.user.username
            rol = uyelik.role
            uyelik_id = uyelik.pk
            uyelik.delete()
            denetim_yaz(
                actor=request.user, mission=mission,
                action=AuditLog.Action.MEMBER_REMOVED,
                object_type="MissionMember", object_id=uyelik_id,
                onceki={"username": kullanici_adi, "role": rol},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class DetectionReviewView(generics.GenericAPIView):
    """GET  /api/detections/{id}/reviews/ -- tespitin incelemeleri
    PUT  /api/detections/{id}/reviews/ -- kendi kararini yaz/guncelle

    Her kullanici KENDI kararini yazar; baskasinin karari ezilmez.
    """

    serializer_class = ReviewYazSerializer

    def _tespiti_al(self, request, detection_id, *, yazma=False):
        detection = get_object_or_404(
            Detection.objects.select_related("inference_run__mission"),
            pk=detection_id,
            inference_run__mission__members__user=request.user,
        )
        mission = detection.inference_run.mission
        gorevi_al_veya_404(request.user, mission.id, yazma=yazma)
        return detection, mission

    def get(self, request, detection_id):
        detection, _ = self._tespiti_al(request, detection_id)
        incelemeler = (
            Review.objects.filter(detection=detection)
            .select_related("reviewer")
            .order_by("-updated_at")
        )
        return Response(ReviewSerializer(incelemeler, many=True).data)

    def put(self, request, detection_id):
        detection, mission = self._tespiti_al(request, detection_id, yazma=True)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        veri = serializer.validated_data

        with transaction.atomic():
            mevcut = Review.objects.filter(
                detection=detection, reviewer=request.user
            ).first()
            onceki = (
                {"decision": mevcut.decision, "note": mevcut.note} if mevcut else {}
            )
            inceleme, olusturuldu = Review.objects.update_or_create(
                detection=detection,
                reviewer=request.user,
                defaults={"decision": veri["decision"], "note": veri.get("note", "")},
            )
            denetim_yaz(
                actor=request.user, mission=mission,
                action=(
                    AuditLog.Action.REVIEW_CREATED if olusturuldu
                    else AuditLog.Action.REVIEW_UPDATED
                ),
                nesne=inceleme,
                onceki=onceki,
                sonraki={"decision": inceleme.decision, "note": inceleme.note},
                ek={"detection_id": detection.id},
            )
        return Response(
            ReviewSerializer(inceleme).data,
            status=status.HTTP_201_CREATED if olusturuldu else status.HTTP_200_OK,
        )


class RunReviewListView(generics.ListAPIView):
    """GET /api/runs/{id}/reviews/ -- kosudaki tum incelemeler.

    Arayuz sonuc ekraninda her tespit icin ayri istek atmasin diye var.
    """

    serializer_class = ReviewSerializer

    def get_queryset(self):
        run = get_object_or_404(
            InferenceRun, pk=self.kwargs["run_id"],
            mission__members__user=self.request.user,
        )
        return (
            Review.objects.filter(detection__inference_run=run)
            .select_related("reviewer", "detection")
            .order_by("detection_id", "-updated_at")
        )


class MissionFindingListCreateView(generics.ListAPIView):
    """GET  /api/missions/{id}/findings/ -- bulgular
    POST /api/missions/{id}/findings/ -- bulgu olustur (yazma yetkisi)
    """

    serializer_class = FindingSerializer

    def get_queryset(self):
        mission = gorevi_al_veya_404(self.request.user, self.kwargs["mission_id"])
        queryset = (
            Finding.objects.filter(mission=mission)
            .select_related("created_by")
            .order_by("-created_at", "-id")
        )
        # Demo ve gercek ayri sorgulanabilsin: harita katmanlari bunu kullanir.
        sadece = self.request.query_params.get("demo")
        if sadece == "true":
            queryset = queryset.filter(location_source=Finding.LocationSource.DEMO)
        elif sadece == "false":
            queryset = queryset.exclude(location_source=Finding.LocationSource.DEMO)
        return queryset

    def post(self, request, mission_id):
        mission = gorevi_al_veya_404(request.user, mission_id, yazma=True)
        serializer = FindingYazSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        veri = serializer.validated_data

        detection = veri.get("detection")
        if detection is not None and detection.inference_run.mission_id != mission.id:
            raise ValidationError({"detection": "Tespit bu goreve ait degil."})

        with transaction.atomic():
            bulgu = Finding.objects.create(
                mission=mission,
                title=veri.get("title", ""),
                note=veri.get("note", ""),
                status=veri.get("status", Finding.Status.CANDIDATE),
                location=_nokta_yap(veri.get("latitude"), veri.get("longitude")),
                location_source=veri["location_source"],
                location_note=veri.get("location_note", ""),
                detection=detection,
                created_by=request.user,
            )
            denetim_yaz(
                actor=request.user, mission=mission,
                action=AuditLog.Action.FINDING_CREATED, nesne=bulgu,
                sonraki={
                    "title": bulgu.title,
                    "status": bulgu.status,
                    "location_source": bulgu.location_source,
                },
            )
        return Response(FindingSerializer(bulgu).data, status=status.HTTP_201_CREATED)


class FindingDetailView(generics.GenericAPIView):
    """PATCH/DELETE /api/findings/{id}/ -- yazma yetkisi ister."""

    serializer_class = FindingYazSerializer

    def _bulguyu_al(self, request, finding_id):
        bulgu = get_object_or_404(
            Finding.objects.select_related("mission"),
            pk=finding_id,
            mission__members__user=request.user,
        )
        gorevi_al_veya_404(request.user, bulgu.mission_id, yazma=True)
        return bulgu

    def patch(self, request, finding_id):
        bulgu = self._bulguyu_al(request, finding_id)
        serializer = FindingYazSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        veri = serializer.validated_data

        onceki = {
            "title": bulgu.title,
            "status": bulgu.status,
            "location_source": bulgu.location_source,
        }
        with transaction.atomic():
            bulgu.title = veri.get("title", bulgu.title)
            bulgu.note = veri.get("note", bulgu.note)
            bulgu.status = veri.get("status", bulgu.status)
            bulgu.location = _nokta_yap(veri.get("latitude"), veri.get("longitude"))
            bulgu.location_source = veri["location_source"]
            bulgu.location_note = veri.get("location_note", bulgu.location_note)
            # Konum degistiyse eski kume sonucu gecersizdir.
            bulgu.cluster_id = None
            bulgu.cluster_key = ""
            bulgu.clustered_at = None
            bulgu.save()
            denetim_yaz(
                actor=request.user, mission=bulgu.mission,
                action=AuditLog.Action.FINDING_UPDATED, nesne=bulgu,
                onceki=onceki,
                sonraki={
                    "title": bulgu.title,
                    "status": bulgu.status,
                    "location_source": bulgu.location_source,
                },
            )
        return Response(FindingSerializer(bulgu).data)

    def delete(self, request, finding_id):
        bulgu = self._bulguyu_al(request, finding_id)
        with transaction.atomic():
            mission = bulgu.mission
            bulgu_id = bulgu.pk
            onceki = {"title": bulgu.title, "location_source": bulgu.location_source}
            bulgu.delete()
            denetim_yaz(
                actor=request.user, mission=mission,
                action=AuditLog.Action.FINDING_DELETED,
                object_type="Finding", object_id=bulgu_id, onceki=onceki,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MissionClusterView(generics.GenericAPIView):
    """GET  /api/missions/{id}/clusters/ -- mevcut kume ozeti
    POST /api/missions/{id}/clusters/ -- kumelemeyi calistir (yazma yetkisi)
    """

    serializer_class = None

    def get(self, request, mission_id):
        mission = gorevi_al_veya_404(request.user, mission_id)
        return Response({
            "esik_metre_varsayilan": VARSAYILAN_ESIK_METRE,
            "clusters": kume_ozeti(mission),
        })

    def post(self, request, mission_id):
        mission = gorevi_al_veya_404(request.user, mission_id, yazma=True)

        ham_esik = request.data.get("esik_metre", VARSAYILAN_ESIK_METRE)
        try:
            esik = float(ham_esik)
        except (TypeError, ValueError):
            raise ValidationError({"esik_metre": "Sayi bekleniyor."})
        if not 0 < esik <= 100000:
            raise ValidationError({"esik_metre": "(0, 100000] araliginda olmali."})

        with transaction.atomic():
            sonuc = gorevi_kumele(mission, esik_metre=esik, aktor=request.user)
            denetim_yaz(
                actor=request.user, mission=mission,
                action=AuditLog.Action.CLUSTER_RUN,
                object_type="Mission", object_id=mission.id,
                ek={
                    "esik_metre": esik,
                    "kume_sayisi": sonuc["kume_sayisi"],
                    "kumelenen_bulgu": sonuc["kumelenen_bulgu"],
                },
            )
        sonuc["clusters"] = kume_ozeti(mission)
        return Response(sonuc)


class MissionAuditListView(generics.ListAPIView):
    """GET /api/missions/{id}/audit/ -- SALT OKUNUR faaliyet gecmisi.

    Yazma ucu YOKTUR: denetim kaydi yalnizca servis katmanindan, islemi yapan
    kodla ayni transaction icinde yazilir.
    """

    serializer_class = AuditLogSerializer

    def get_queryset(self):
        mission = gorevi_al_veya_404(self.request.user, self.kwargs["mission_id"])
        return (
            AuditLog.objects.filter(mission=mission)
            .select_related("actor")
            .order_by("-created_at", "-id")
        )
