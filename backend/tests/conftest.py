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
