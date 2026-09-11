from rest_framework import serializers

from .models import Frame, Mission


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
