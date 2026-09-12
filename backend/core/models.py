from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.core.exceptions import ValidationError
from django.db import models
from django.dispatch import receiver


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


class MissionMember(models.Model):
    """Bir gorevin kullanicilari ve rolleri.

    Hafta 5'e kadar erisim tek olcute bagliydi: gorevi kim olusturduysa onu
    goruyordu. Bu, arama kurtarma gibi ekip isi bir baglamda yetersiz -- bir
    gorevi birden fazla operator izler, bazilari yalnizca bakar. Uyelik kaydi
    bu ayrimi tasir.

    Mission.created_by SILINMEDI: gecmis kayitlarin kim tarafindan acildigini
    aciklamaya devam eder. Ama ERISIM artik created_by'a degil bu tabloya
    bakar; ikisi migration ile ayni noktadan baslatilir.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Sahip"
        OPERATOR = "operator", "Operator"
        VIEWER = "viewer", "Izleyici"

    #: Yazma yetkisi olan roller. Tek yerde durur ki izin kontrolleri
    #: birbirinden farkli tanimlar kullanmasin.
    WRITE_ROLES = (Role.OWNER, Role.OPERATOR)
    #: Uyelik ve rol yonetebilen roller.
    ADMIN_ROLES = (Role.OWNER,)

    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mission_memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_mission_members",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["mission", "user"], name="uniq_mission_member"
            )
        ]
        indexes = [
            models.Index(fields=["user", "mission"], name="mission_member_user_idx")
        ]

    def __str__(self):
        return f"{self.user_id}@{self.mission_id} ({self.role})"


class Review(models.Model):
    """Bir tespit icin operator karari.

    Detection KAYDINA DOKUNMAZ. Model ciktisi ile insan yargisi ayri
    tablolarda durur; ayni alana yazilsalardi modelin ne buldugu ile
    operatorun ne dusundugu geri donulmez bicimde karisirdi ve gecmis
    olcumler yeniden uretilemezdi.

    Tekillik (tespit, inceleyen) ciftinde: her operator kendi kararini
    gunceller, baskasinin kararini EZMEZ. Boylece iki operatorun ayni tespit
    hakkinda anlasamadigi bilgisi korunur -- bu, arama kurtarmada atilacak
    bir bilgi degil. Karar degisiklikleri AuditLog'da izlenir.
    """

    class Decision(models.TextChoices):
        ACCEPTED = "accepted", "Dogrulandi"
        REJECTED = "rejected", "Reddedildi"
        UNCERTAIN = "uncertain", "Belirsiz"

    detection = models.ForeignKey(
        Detection, on_delete=models.CASCADE, related_name="reviews"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    decision = models.CharField(max_length=20, choices=Decision.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["detection", "reviewer"], name="uniq_review_per_reviewer"
            )
        ]
        indexes = [
            models.Index(fields=["detection", "decision"], name="review_detection_idx")
        ]

    def __str__(self):
        return f"{self.detection_id}/{self.reviewer_id}: {self.decision}"


class Finding(models.Model):
    """Haritada gosterilebilen, KAYNAGI BELLI cografi bulgu.

    Bu modelin en kritik alani koordinatin kendisi degil, `location_source`.
    Elimizdeki veri kumesinde hicbir goruntude EXIF GPS yok (Hafta 5 taramasi:
    1579 goruntu, 0 koordinat). Dolayisiyla kaydedilebilecek her koordinat ya
    operatorun elle girdigi ya da gosterim amacli uretilmis bir degerdir.
    Kaynak saklanmazsa bu iki tur ile gercek olculmus GPS birbirinden ayirt
    edilemez -- ve arama kurtarma baglaminda "bu nokta nereden geldi" sorusu
    koordinatin kendisinden daha onemlidir.

    KONUM YOKLUGU BIR DEGERDIR. location NULL olabilir ve bu "0, 0" DEMEK
    DEGILDIR; 0,0 Gine Korfezi'nde gercek bir noktadir. Asagidaki kisit ikisini
    birbirine karistirmayi veritabani seviyesinde engeller: konum yoksa kaynak
    'none' olmak ZORUNDA, konum varsa kaynak 'none' OLAMAZ.

    Detection kutusundan otomatik koordinat URETILMEZ. Piksel ile dunya
    arasinda donusum icin kameranin konumu, irtifasi, yonelimi ve gorus acisi
    gerekir; bunlarin hicbiri elimizde yok.
    """

    class LocationSource(models.TextChoices):
        NONE = "none", "Konum yok"
        EXIF = "exif", "Goruntu EXIF GPS"
        FLIGHT_LOG = "flight_log", "Ucus gunlugu"
        MANUAL = "manual", "Operator girisi"
        DEMO = "demo", "Demo / sentetik"

    class Status(models.TextChoices):
        CANDIDATE = "candidate", "Aday"
        CONFIRMED = "confirmed", "Dogrulandi"
        DISMISSED = "dismissed", "Elendi"

    #: Gercek dunyada olculmus sayilan kaynaklar. Demo ve operator girisi bu
    #: kumede DEGIL: biri uydurma, digeri beyan.
    MEASURED_SOURCES = (LocationSource.EXIF, LocationSource.FLIGHT_LOG)

    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="findings")
    title = models.CharField(max_length=200, blank=True)
    note = models.TextField(blank=True)

    # geography=True: mesafe sorgulari METRE cinsinden calisir. Geometry
    # kullanilsaydi ayni sorgu DERECE doner ve "50 metre" diye yazilan esik
    # sessizce yanlis olurdu. spatial_index varsayilan olarak acik -> GiST.
    location = gis_models.PointField(
        srid=4326, geography=True, null=True, blank=True, spatial_index=True
    )
    location_source = models.CharField(
        max_length=20, choices=LocationSource.choices, default=LocationSource.NONE
    )
    location_note = models.CharField(max_length=300, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CANDIDATE
    )

    # Bulgunun hangi tespitten/incelemeden dogdugu. Ikisi de istege bagli:
    # operator dogrudan da bulgu acabilir.
    detection = models.ForeignKey(
        Detection, on_delete=models.SET_NULL, null=True, blank=True, related_name="findings"
    )
    review = models.ForeignKey(
        Review, on_delete=models.SET_NULL, null=True, blank=True, related_name="findings"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="findings",
    )

    # Kumeleme sonucu. cluster_key kumelemenin hangi kosusundan geldigini,
    # cluster_id o kosudaki bagli bileseni gosterir. Kumeleme calismadan once
    # ikisi de bostur.
    cluster_id = models.IntegerField(null=True, blank=True)
    cluster_key = models.CharField(max_length=100, blank=True)
    clustered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Konum yoklugu ile "0,0" birbirine karismasin; kaynaksiz koordinat
            # ve koordinatsiz kaynak iddiasi da olusmasin.
            models.CheckConstraint(
                condition=(
                    models.Q(location__isnull=True, location_source="none")
                    | models.Q(location__isnull=False) & ~models.Q(location_source="none")
                ),
                name="finding_konum_kaynak_tutarli",
            )
        ]
        indexes = [
            models.Index(fields=["mission", "status"], name="finding_mission_status_idx"),
            models.Index(fields=["mission", "cluster_key"], name="finding_cluster_idx"),
        ]

    @property
    def is_demo(self):
        """Gosterim amacli uretilmis koordinat mi."""
        return self.location_source == self.LocationSource.DEMO

    @property
    def has_measured_location(self):
        """Koordinat gercekten olculmus bir kaynaktan mi geliyor."""
        return self.location_source in self.MEASURED_SOURCES

    def __str__(self):
        return f"#{self.pk} {self.mission_id} ({self.location_source})"


class AuditLog(models.Model):
    """Kritik islemlerin EKLEMELI kaydi.

    Degistirilemez ve silinemez: save() yalnizca ilk yazmaya izin verir,
    delete() her zaman hata verir. Bu, ORM seviyesinde bir koruma -- veritabani
    yoneticisi yine mudahale edebilir; amac uygulama kodunun veya bir API ucunun
    kazara ya da kotu niyetle gecmisi degistirmesini engellemek.

    `changes` alanina ham nesne DOKULMEZ: yalnizca degisen alanlarin onceki ve
    sonraki degerlerinin ozeti yazilir ve hassas anahtarlar temizlenir. Parola,
    token, dosya icerigi ve gereksiz kisisel veri bu tabloya girmez.
    """

    class Action(models.TextChoices):
        MEMBER_ADDED = "member_added", "Uye eklendi"
        MEMBER_ROLE_CHANGED = "member_role_changed", "Uye rolu degisti"
        MEMBER_REMOVED = "member_removed", "Uye cikarildi"
        REVIEW_CREATED = "review_created", "Inceleme olusturuldu"
        REVIEW_UPDATED = "review_updated", "Inceleme guncellendi"
        FINDING_CREATED = "finding_created", "Bulgu olusturuldu"
        FINDING_UPDATED = "finding_updated", "Bulgu guncellendi"
        FINDING_DELETED = "finding_deleted", "Bulgu silindi"
        CLUSTER_RUN = "cluster_run", "Kumeleme calistirildi"
        RUN_STARTED = "run_started", "Tarama baslatildi"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    mission = models.ForeignKey(
        Mission, on_delete=models.CASCADE, related_name="audit_entries"
    )
    action = models.CharField(max_length=40, choices=Action.choices)
    object_type = models.CharField(max_length=40)
    object_id = models.CharField(max_length=40, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["mission", "-created_at"], name="audit_mission_time_idx")
        ]
        ordering = ["-created_at", "-id"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Denetim kaydi degistirilemez.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Denetim kaydi silinemez.")

    def __str__(self):
        return f"#{self.pk} {self.action} {self.object_type}:{self.object_id}"


@receiver(models.signals.post_save, sender=Mission)
def gorev_sahibini_uye_yap(sender, instance, created, **kwargs):
    """Gorev olusturulunca olusturan kullanici owner uyesi olur.

    Bunu view'da degil burada yapmanin nedeni: gorev yalnizca API'den
    olusturulmuyor. Yonetim komutlari, fixture'lar ve testler de dogrudan ORM
    uzerinden gorev aciyor. Kural view'da kalsaydi bu yollardan acilan her
    gorev SAHIPSIZ kalirdi -- yani olusturani dahil kimse goremezdi. Kurali
    modele baglayinca "olusturani olan her gorevin bir sahibi vardir"
    degismezi butun kod yollarinda gecerli oluyor.
    """
    if not created or instance.created_by_id is None:
        return
    MissionMember.objects.get_or_create(
        mission=instance,
        user_id=instance.created_by_id,
        defaults={
            "role": MissionMember.Role.OWNER,
            "added_by_id": instance.created_by_id,
        },
    )
