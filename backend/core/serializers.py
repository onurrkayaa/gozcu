from django.db.models import Count
from rest_framework import serializers

from .models import Detection, Frame, InferenceRun, Mission, ModelVersion


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
        )
        read_only_fields = (
            "id",
            "created_by",
            "created_at",
            "updated_at",
            "frame_count",
            "frame_counts",
            "latest_run",
        )

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
