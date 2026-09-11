from django.conf import settings
from django.db import models


def frame_upload_path(instance, filename):
    """Her gorevin goruntuleri kendi klasorunde dursun."""
    return f"missions/{instance.mission_id}/{filename}"


class Mission(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="missions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Frame(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Bekliyor"
        QUEUED = "queued", "Kuyrukta"
        PROCESSING = "processing", "Isleniyor"
        DONE = "done", "Tamam"
        FAILED = "failed", "Basarisiz"

    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="frames")
    image = models.ImageField(upload_to=frame_upload_path)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64, db_index=True)
    width = models.IntegerField()
    height = models.IntegerField()
    captured_at = models.DateTimeField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    altitude_m = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["mission", "sha256"], name="uniq_frame_sha256_per_mission"
            )
        ]
        indexes = [models.Index(fields=["mission", "status"], name="frame_mission_status_idx")]

    def __str__(self):
        return f"{self.original_filename} ({self.mission_id})"


class ModelVersion(models.Model):
    name = models.CharField(max_length=200, unique=True)
    weights_path = models.CharField(max_length=500)
    framework = models.CharField(max_length=50)
    input_size = models.IntegerField()
    tile_size = models.IntegerField()
    overlap_ratio = models.FloatField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class InferenceRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Bekliyor"
        RUNNING = "running", "Calisiyor"
        DONE = "done", "Tamam"
        FAILED = "failed", "Basarisiz"

    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="runs")
    model_version = models.ForeignKey(
        ModelVersion, on_delete=models.PROTECT, related_name="runs"
    )
    conf_threshold = models.FloatField()
    iou_threshold = models.FloatField()
    tile_size = models.IntegerField()
    overlap_ratio = models.FloatField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    frames_total = models.IntegerField(default=0)
    frames_done = models.IntegerField(default=0)
    frames_failed = models.IntegerField(default=0)

    def __str__(self):
        return f"#{self.pk} {self.mission_id} / {self.model_version_id} ({self.status})"


class Detection(models.Model):
    inference_run = models.ForeignKey(
        InferenceRun, on_delete=models.CASCADE, related_name="detections"
    )
    frame = models.ForeignKey(Frame, on_delete=models.CASCADE, related_name="detections")
    score = models.FloatField()
    # Kutu koordinatlari ORIJINAL goruntu duzleminde, karo duzleminde degil.
    x1 = models.IntegerField()
    y1 = models.IntegerField()
    x2 = models.IntegerField()
    y2 = models.IntegerField()
    tile_row = models.IntegerField(null=True, blank=True)
    tile_col = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["inference_run", "-score"], name="detection_run_score_idx")
        ]

    def __str__(self):
        return f"#{self.pk} frame={self.frame_id} score={self.score:.3f}"
