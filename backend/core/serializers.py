from django.db.models import Count
from rest_framework import serializers

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


class MissionRunSummarySerializer(serializers.ModelSerializer):
    """Gorev listesinde kosuyu ozetler. InferenceRunSerializer'in alt kumesi."""

    model_version_name = serializers.CharField(source="model_version.name", read_only=True)

    class Meta:
        model = InferenceRun
        fields = (
            "id",
            "status",
            "model_version",
            "model_version_name",
            "conf_threshold",
            "frames_total",
            "frames_done",
            "frames_failed",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields


class MissionSerializer(serializers.ModelSerializer):
    """Gorev. Sayimlar ve son kosu SALT OKUNUR ektir; yazma yuzeyi degismedi.

    frame_counts, Frame.Status degerlerinin TAMAMINI anahtar olarak tasir --
    sifir olan durum da anahtar olarak bulunur, boylece istemci eksik anahtar
    icin savunma kodu yazmak zorunda kalmaz.
    """

    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    frame_count = serializers.SerializerMethodField()
    frame_counts = serializers.SerializerMethodField()
    latest_run = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Mission
        fields = (
            "id",
            "name",
            "description",
            "created_by",
            "created_at",
            "updated_at",
            "frame_count",
            "frame_counts",
            "latest_run",
            "my_role",
        )
        read_only_fields = (
            "id",
            "created_by",
            "created_at",
            "updated_at",
            "frame_count",
            "frame_counts",
            "latest_run",
            "my_role",
        )

    def get_my_role(self, mission):
        """Istekte bulunan kullanicinin bu gorevdeki rolu.

        Arayuzun hangi denetimleri gosterecegini buna gore secmesi icin var.
        Yetki kararini bu alan VERMEZ -- yetki her uctan ayrica dogrulanir;
        bu alan yalnizca kullaniciya calismayacak dugme gostermemek icin.
        """
        istek = self.context.get("request")
        if istek is None or not istek.user.is_authenticated:
            return None
        for uyelik in mission.members.all():
            if uyelik.user_id == istek.user.id:
                return uyelik.role
        return None

    def get_frame_count(self, mission):
        # Annotate edilmisse ek sorgu yok; edilmemisse (tekil kullanim) say.
        sayi = getattr(mission, "frame_count_annotated", None)
        if sayi is not None:
            return sayi
        return mission.frames.count()

    def get_frame_counts(self, mission):
        sayimlar = {durum: 0 for durum in Frame.Status.values}
        for durum in Frame.Status.values:
            annotated = getattr(mission, f"frames_{durum}_annotated", None)
            if annotated is None:
                sayimlar = None
                break
            sayimlar[durum] = annotated
        if sayimlar is not None:
            return sayimlar

        sayimlar = {durum: 0 for durum in Frame.Status.values}
        for satir in mission.frames.values("status").annotate(adet=Count("id")):
            sayimlar[satir["status"]] = satir["adet"]
        return sayimlar

    def get_latest_run(self, mission):
        # View prefetch ettiginde liste bellekte; etmediginde tek sorgu.
        kosular = getattr(mission, "son_kosular", None)
        if kosular is None:
            kosu = (
                mission.runs.select_related("model_version")
                .order_by("-started_at", "-id")
                .first()
            )
        else:
            kosu = kosular[0] if kosular else None
        if kosu is None:
            return None
        return MissionRunSummarySerializer(kosu).data


class FrameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Frame
        fields = (
            "id",
            "mission",
            "image",
            "original_filename",
            "sha256",
            "width",
            "height",
            "captured_at",
            "latitude",
            "longitude",
            "altitude_m",
            "status",
            "created_at",
        )
        read_only_fields = fields


class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = (
            "id",
            "name",
            "framework",
            "input_size",
            "tile_size",
            "overlap_ratio",
            "notes",
            "created_at",
        )
        read_only_fields = fields


class InferenceRunSerializer(serializers.ModelSerializer):
    model_version_name = serializers.CharField(source="model_version.name", read_only=True)

    class Meta:
        model = InferenceRun
        fields = (
            "id",
            "mission",
            "model_version",
            "model_version_name",
            "status",
            "conf_threshold",
            "iou_threshold",
            "tile_size",
            "overlap_ratio",
            "frames_total",
            "frames_done",
            "frames_failed",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields


class RunCreateSerializer(serializers.Serializer):
    """Tarama baslatma govdesi. Kosu parametreleri burada dogrulanir."""

    model_version_id = serializers.PrimaryKeyRelatedField(
        queryset=ModelVersion.objects.all(), source="model_version"
    )
    conf_threshold = serializers.FloatField(min_value=0.0, max_value=1.0, default=0.25)
    iou_threshold = serializers.FloatField(min_value=0.0, max_value=1.0, default=0.45)
    tile_size = serializers.IntegerField(min_value=32, max_value=4096, default=512)
    overlap_ratio = serializers.FloatField(min_value=0.0, max_value=0.9, default=0.2)


class DetectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Detection
        fields = (
            "id",
            "inference_run",
            "frame",
            "score",
            "x1",
            "y1",
            "x2",
            "y2",
            "tile_row",
            "tile_col",
            "created_at",
        )
        read_only_fields = fields


class KullaniciOzetSerializer(serializers.Serializer):
    """Kullanicinin arayuzde gosterilebilecek EN AZ bilgisi.

    E-posta DONDURULMEZ: uye listesi gorevdeki herkese aciktir ve e-posta
    adresi, arayuzun hicbir yerinde ihtiyac duyulmayan kisisel bir veridir.
    """

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)


class MissionMemberSerializer(serializers.ModelSerializer):
    user = KullaniciOzetSerializer(read_only=True)

    class Meta:
        model = MissionMember
        fields = ("id", "mission", "user", "role", "created_at", "updated_at")
        read_only_fields = fields


class MissionMemberYazSerializer(serializers.Serializer):
    """Uye ekleme ve rol guncelleme govdesi."""

    username = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=MissionMember.Role.choices)


class MissionMemberRolSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=MissionMember.Role.choices)


class ReviewSerializer(serializers.ModelSerializer):
    reviewer = KullaniciOzetSerializer(read_only=True)

    class Meta:
        model = Review
        fields = (
            "id", "detection", "reviewer", "decision", "note",
            "created_at", "updated_at",
        )
        read_only_fields = fields


class ReviewYazSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=Review.Decision.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class FindingSerializer(serializers.ModelSerializer):
    """Bulgu.

    Konum GeoJSON noktasi olarak doner: `{"type": "Point", "coordinates":
    [boylam, enlem]}`. GeoJSON sirasi BOYLAM ONCE'dir (RFC 7946); form
    alanlarindaki enlem/boylam sirasiyla karistirilmamalidir. Konum yoksa alan
    `null` doner -- "0, 0" DEGIL.
    """

    created_by = KullaniciOzetSerializer(read_only=True)
    location = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    is_demo = serializers.BooleanField(read_only=True)
    has_measured_location = serializers.BooleanField(read_only=True)

    class Meta:
        model = Finding
        fields = (
            "id", "mission", "title", "note", "status",
            "location", "latitude", "longitude",
            "location_source", "location_note",
            "is_demo", "has_measured_location",
            "detection", "review", "created_by",
            "cluster_id", "cluster_key", "clustered_at",
            "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_location(self, finding):
        if finding.location is None:
            return None
        # GeoJSON: [boylam, enlem]
        return {"type": "Point", "coordinates": [finding.location.x, finding.location.y]}

    def get_latitude(self, finding):
        return None if finding.location is None else finding.location.y

    def get_longitude(self, finding):
        return None if finding.location is None else finding.location.x


class FindingYazSerializer(serializers.Serializer):
    """Bulgu olusturma/guncelleme govdesi.

    Koordinat, GeoJSON dizisi yerine AYRI enlem/boylam alanlariyla alinir:
    dizideki sira kolayca ters yazilir ve hata sessizce gecer. Ayri alanlarda
    ad, sirayi belirsiz birakmaz.
    """

    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Finding.Status.choices, required=False)
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False, allow_null=True)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False, allow_null=True)
    location_source = serializers.ChoiceField(choices=Finding.LocationSource.choices)
    location_note = serializers.CharField(max_length=300, required=False, allow_blank=True)
    detection = serializers.PrimaryKeyRelatedField(
        queryset=Detection.objects.all(), required=False, allow_null=True
    )

    def validate(self, veri):
        enlem = veri.get("latitude")
        boylam = veri.get("longitude")
        kaynak = veri.get("location_source")

        koordinat_var = enlem is not None and boylam is not None
        if (enlem is None) != (boylam is None):
            raise serializers.ValidationError(
                {"latitude": "Enlem ve boylam birlikte verilmeli."}
            )

        if koordinat_var and kaynak == Finding.LocationSource.NONE:
            raise serializers.ValidationError(
                {"location_source": "Koordinat verildiginde kaynak 'none' olamaz."}
            )
        if not koordinat_var and kaynak != Finding.LocationSource.NONE:
            raise serializers.ValidationError(
                {"location_source": "Koordinat yokken kaynak 'none' olmali."}
            )
        # EXIF ve ucus gunlugu OLCULMUS kaynaklardir; operator bunlari elle
        # secip uydurma bir koordinati olculmus gibi gosteremez.
        if kaynak in (Finding.LocationSource.EXIF, Finding.LocationSource.FLIGHT_LOG):
            raise serializers.ValidationError(
                {"location_source": (
                    "Olculmus kaynaklar elle secilemez; koordinat ancak alim "
                    "hattindan gelirse bu kaynakla saklanir."
                )}
            )
        return veri


class AuditLogSerializer(serializers.ModelSerializer):
    actor = KullaniciOzetSerializer(read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = (
            "id", "mission", "actor", "action", "action_display",
            "object_type", "object_id", "changes", "created_at",
        )
        read_only_fields = fields
