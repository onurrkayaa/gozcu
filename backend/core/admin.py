from django.contrib import admin

from .models import Detection, Frame, InferenceRun, Mission, ModelVersion


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_by", "created_at")
    search_fields = ("name",)


@admin.register(Frame)
class FrameAdmin(admin.ModelAdmin):
    list_display = ("id", "original_filename", "mission", "status", "width", "height", "created_at")
    list_filter = ("status", "mission")
    search_fields = ("original_filename", "sha256")


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "framework", "input_size", "tile_size", "overlap_ratio")
    search_fields = ("name",)


@admin.register(InferenceRun)
class InferenceRunAdmin(admin.ModelAdmin):
    list_display = ("id", "mission", "model_version", "status", "frames_total", "frames_done", "started_at")
    list_filter = ("status",)


@admin.register(Detection)
class DetectionAdmin(admin.ModelAdmin):
    list_display = ("id", "inference_run", "frame", "score", "x1", "y1", "x2", "y2")
    list_filter = ("inference_run",)
