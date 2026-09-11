import pytest

from core.models import Mission
from core.services import ingest_frame

pytestmark = pytest.mark.django_db


def test_image_without_exif_is_ingested_with_null_metadata(user, make_image):
    """Veri kumemizdeki goruntulerin cogunda EXIF yok; bu normal yol."""
    mission = Mission.objects.create(name="EXIF'siz gorev", created_by=user)

    frame, duplicate = ingest_frame(mission, make_image(name="exifsiz.jpg"))

    assert duplicate is False
    assert frame.pk is not None
    assert frame.captured_at is None
    assert frame.latitude is None
    assert frame.longitude is None
    assert frame.altitude_m is None
    assert (frame.width, frame.height) == (64, 48)
