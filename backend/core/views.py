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

from .models import Detection, Frame, InferenceRun, Mission, ModelVersion
from .serializers import (
    DetectionSerializer,
    FrameSerializer,
    InferenceRunSerializer,
    MissionSerializer,
    ModelVersionSerializer,
    RunCreateSerializer,
)
from .services import InvalidImageError, ingest_frame
from .tasks import run_inference


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
    sayim_annotasyonlari = {
        f"frames_{durum}_annotated": Count(
            "frames", filter=Q(frames__status=durum), distinct=True
        )
        for durum in Frame.Status.values
    }
    return (
        Mission.objects.filter(created_by=user)
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

    def get_mission(self):
        return get_object_or_404(
            Mission, pk=self.kwargs["mission_id"], created_by=self.request.user
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
        mission = self.get_mission()
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
        mission = get_object_or_404(
            Mission, pk=self.kwargs["mission_id"], created_by=self.request.user
        )
        return (
            InferenceRun.objects.filter(mission=mission)
            .select_related("model_version")
            .order_by("-started_at", "-id")
        )

    def post(self, request, mission_id):
        # Sahiplik queryset'te suzuluyor: baskasinin gorevi 404 doner, "var ama
        # yetkin yok" bilgisi bile sizmaz.
        mission = get_object_or_404(Mission, pk=mission_id, created_by=request.user)

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
            mission__created_by=self.request.user
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
            InferenceRun, pk=self.kwargs["run_id"], mission__created_by=self.request.user
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
        frame = get_object_or_404(
            Frame, pk=frame_id, mission__created_by=request.user
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
