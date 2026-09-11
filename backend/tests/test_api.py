import pytest
from django.urls import reverse

from core.models import Frame, Mission

pytestmark = pytest.mark.django_db


def test_health_returns_200_with_database_status(api_client):
    response = api_client.get(reverse("health"))
    assert response.status_code == 200
    assert response.data["status"] == "ok"
    assert response.data["database"] == "ok"


def test_mission_list_requires_authentication(api_client):
    response = api_client.get(reverse("mission-list"))
    assert response.status_code == 401


def test_create_mission_assigns_created_by(auth_client, user):
    response = auth_client.post(
        reverse("mission-list"), {"name": "Kayip yurüyüscu", "description": "Test"}
    )
    assert response.status_code == 201
    mission = Mission.objects.get(pk=response.data["id"])
    assert mission.created_by == user
    assert response.data["created_by"] == user.id


def test_other_users_mission_is_not_listed(auth_client, other_user):
    Mission.objects.create(name="Baskasinin gorevi", created_by=other_user)
    response = auth_client.get(reverse("mission-list"))
    assert response.status_code == 200
    assert response.data["count"] == 0


def test_upload_creates_frame_with_dimensions_read_from_file(auth_client, user, make_image):
    mission = Mission.objects.create(name="Gorev", created_by=user)
    url = reverse("mission-frames", args=[mission.id])
    # Istemci yanlis olcu iddia etse bile dosyadan okunan deger kazanmali.
    response = auth_client.post(
        url, {"images": make_image(width=64, height=48), "width": 9999, "height": 9999}
    )
    assert response.status_code == 201
    assert response.data[0]["duplicate"] is False
    assert (response.data[0]["width"], response.data[0]["height"]) == (64, 48)
    frame = Frame.objects.get(pk=response.data[0]["id"])
    assert (frame.width, frame.height) == (64, 48)


def test_new_frame_status_is_pending(auth_client, user, make_image):
    mission = Mission.objects.create(name="Gorev", created_by=user)
    response = auth_client.post(
        reverse("mission-frames", args=[mission.id]), {"images": make_image()}
    )
    frame = Frame.objects.get(pk=response.data[0]["id"])
    assert frame.status == Frame.Status.PENDING


def test_uploading_same_file_twice_is_deduplicated(auth_client, user, make_image):
    mission = Mission.objects.create(name="Gorev", created_by=user)
    url = reverse("mission-frames", args=[mission.id])

    first = auth_client.post(url, {"images": make_image(name="ayni.jpg")})
    second = auth_client.post(url, {"images": make_image(name="ayni.jpg")})

    assert first.data[0]["duplicate"] is False
    assert second.data[0]["duplicate"] is True
    assert second.data[0]["id"] == first.data[0]["id"]
    assert Frame.objects.filter(mission=mission).count() == 1


def test_same_file_can_be_uploaded_to_different_missions(auth_client, user, make_image):
    first_mission = Mission.objects.create(name="Gorev 1", created_by=user)
    second_mission = Mission.objects.create(name="Gorev 2", created_by=user)

    first = auth_client.post(
        reverse("mission-frames", args=[first_mission.id]), {"images": make_image(name="a.jpg")}
    )
    second = auth_client.post(
        reverse("mission-frames", args=[second_mission.id]), {"images": make_image(name="a.jpg")}
    )

    assert first.data[0]["duplicate"] is False
    assert second.data[0]["duplicate"] is False
    assert first.data[0]["id"] != second.data[0]["id"]
    assert Frame.objects.count() == 2


def test_upload_of_broken_file_returns_400(auth_client, user):
    from django.core.files.uploadedfile import SimpleUploadedFile

    mission = Mission.objects.create(name="Gorev", created_by=user)
    bozuk = SimpleUploadedFile("notlar.txt", b"bu bir goruntu degil", content_type="text/plain")

    response = auth_client.post(reverse("mission-frames", args=[mission.id]), {"images": bozuk})

    assert response.status_code == 400
    assert Frame.objects.count() == 0
