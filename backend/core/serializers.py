from rest_framework import serializers

from .models import Detection, Frame, InferenceRun, Mission, ModelVersion


class MissionSerializer(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Mission
        fields = ("id", "name", "description", "created_by", "created_at", "updated_at")
        read_only_fields = ("id", "created_by", "created_at", "updated_at")


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
