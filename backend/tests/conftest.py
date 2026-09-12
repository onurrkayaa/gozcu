import io

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def temp_media_root(settings, tmp_path):
    """Testler gercek media/ klasorunu kirletmesin."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture(autouse=True)
def zamanlama_kaydi_kapali(settings):
    """Testler olcum kosusunun zamanlama kaydina yazmasin.

    TASK_TIMING_LOG ortamdan dolu gelebilir (olcum kosusu sirasinda oyle olur).
    Test veritabaninin run_id degerleri gercek kosununkilerle cakisabildigi icin
    test satirlari o dosyaya karisirsa olcum bozulur. Kayda ihtiyaci olan test
    ayari kendisi doldurur."""
    settings.TASK_TIMING_LOG = ""


@pytest.fixture
def make_image():
    """Bellekte kucuk bir test goruntusu uretir; gercek 4000x3000 foto kullanmiyoruz."""

    def _make(name="test.jpg", width=64, height=48, color=(10, 120, 200)):
        buffer = io.BytesIO()
        Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")

    return _make


@pytest.fixture
def user(db):
    return User.objects.create_user(username="onur", password="gizli-parola-123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="baskasi", password="gizli-parola-456")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def celery_eager(settings):
    """Gorevleri kuyruk olmadan, cagrildiklari yerde senkron calistirir."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = False
    from gozcu_api.celery import app

    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = False
    return settings


@pytest.fixture
def model_version(db):
    from core.models import ModelVersion

    return ModelVersion.objects.get(name="fake-v0")


@pytest.fixture
def mission_with_frames(db, user, make_image):
    """Uc kareli bir gorev. Kareler kucuk: karolama mantigi ayrica test ediliyor."""
    from core.models import Mission
    from core.services import ingest_frame

    mission = Mission.objects.create(name="Test gorevi", created_by=user)
    for i in range(3):
        # Her kare farkli renkte olsun ki sha256'lari ayrilsin (tekillik kisiti).
        ingest_frame(mission, make_image(name=f"k{i}.jpg", color=(i * 40, 100, 200)))
    return mission


# --- Hafta 6: uyelik ve rol fixture'lari ---------------------------------


@pytest.fixture
def owner_user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(username="sahip", password="gizli-parola-owner")


@pytest.fixture
def operator_user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(username="operator", password="gizli-parola-oper")


@pytest.fixture
def viewer_user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user(username="izleyici", password="gizli-parola-view")


@pytest.fixture
def yabanci_user(db):
    """Hicbir goreve uye olmayan kullanici."""
    from django.contrib.auth.models import User

    return User.objects.create_user(username="yabanci", password="gizli-parola-yab")


@pytest.fixture
def rollu_gorev(db, owner_user, operator_user, viewer_user, make_image):
    """Uc rolu de dolu, iki kareli bir gorev.

    Gorev owner_user tarafindan aciliyor; owner uyeligini post_save sinyali
    yaziyor, digerleri acikca ekleniyor.
    """
    from core.models import Mission, MissionMember
    from core.services import ingest_frame

    mission = Mission.objects.create(name="Rollu gorev", created_by=owner_user)
    MissionMember.objects.create(
        mission=mission, user=operator_user, role=MissionMember.Role.OPERATOR
    )
    MissionMember.objects.create(
        mission=mission, user=viewer_user, role=MissionMember.Role.VIEWER
    )
    for i in range(2):
        ingest_frame(mission, make_image(name=f"r{i}.jpg", color=(i * 60, 90, 180)))
    return mission


@pytest.fixture
def istemci_yap(api_client):
    """Verilen kullanici adina kimlik dogrulanmis istemci uretir."""

    def _yap(user):
        from rest_framework.test import APIClient

        istemci = APIClient()
        istemci.force_authenticate(user=user)
        return istemci

    return _yap


@pytest.fixture
def tespitli_kosu(rollu_gorev, owner_user, celery_eager, django_capture_on_commit_callbacks):
    """Rollu gorevde tamamlanmis bir kosu ve tespitleri."""
    from django.urls import reverse
    from rest_framework.test import APIClient

    from core.models import Detection, InferenceRun, ModelVersion

    model_version = ModelVersion.objects.get(name="fake-v0")
    istemci = APIClient()
    istemci.force_authenticate(user=owner_user)
    with django_capture_on_commit_callbacks(execute=True):
        yanit = istemci.post(
            reverse("mission-runs", args=[rollu_gorev.id]),
            {"model_version_id": model_version.id, "conf_threshold": 0.0},
            format="json",
        )
    run = InferenceRun.objects.get(pk=yanit.data["run_id"])
    detection = Detection.objects.filter(inference_run=run).first()
    assert detection is not None, "Sahte dedektor hic kutu uretmedi."
    return run, detection
