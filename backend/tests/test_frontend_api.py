"""Hafta 5'te operator arayuzu icin eklenen uclarin testleri.

Uc ekleme de ayni gerekceden dogdu: arayuzun zorunlu akisi mevcut uclarla
tamamlanamiyordu.

1. GET  /api/missions/{id}/         -- gorev ayrintisina dogrudan gidilebilmesi
2. GET  /api/missions/{id}/runs/    -- yeniden yukleme sonrasi kosuyu bulabilmek
3. GET  /api/frames/{id}/image/     -- goruntuyu kimlik dogrulamasiyla okumak

Yeni veri modeli ve migration eklenmedi; uclar mevcut modellerin uzerinde durur.
"""
import pytest
from django.urls import reverse

from core.models import Frame, InferenceRun, Mission

pytestmark = pytest.mark.django_db


@pytest.fixture
def tarama_baslat(django_capture_on_commit_callbacks):
    def _baslat(client, mission, model_version, **ekstra):
        govde = {"model_version_id": model_version.id}
        govde.update(ekstra)
        with django_capture_on_commit_callbacks(execute=True):
            return client.post(
                reverse("mission-runs", args=[mission.id]), govde, format="json"
            )

    return _baslat


# --- Gorev ayrintisi -------------------------------------------------------


def test_gorev_ayrintisi_donuyor(auth_client, mission_with_frames):
    yanit = auth_client.get(reverse("mission-detail", args=[mission_with_frames.id]))
    assert yanit.status_code == 200
    assert yanit.data["id"] == mission_with_frames.id
    assert yanit.data["name"] == mission_with_frames.name


def test_gorev_ayrintisi_kimlik_dogrulama_istiyor(api_client, mission_with_frames):
    yanit = api_client.get(reverse("mission-detail", args=[mission_with_frames.id]))
    assert yanit.status_code in (401, 403)


def test_baskasinin_gorev_ayrintisi_404(api_client, other_user, mission_with_frames):
    api_client.force_authenticate(user=other_user)
    yanit = api_client.get(reverse("mission-detail", args=[mission_with_frames.id]))
    assert yanit.status_code == 404


# --- Kare sayimlari --------------------------------------------------------


def test_gorev_kare_sayimlari_tum_durumlari_tasiyor(auth_client, mission_with_frames):
    """Sifir olan durum da anahtar olarak bulunmali: istemci eksik anahtar
    icin savunma kodu yazmak zorunda kalmasin."""
    yanit = auth_client.get(reverse("mission-detail", args=[mission_with_frames.id]))

    assert yanit.data["frame_count"] == 3
    assert set(yanit.data["frame_counts"]) == set(Frame.Status.values)
    assert yanit.data["frame_counts"]["pending"] == 3
    assert yanit.data["frame_counts"]["done"] == 0
    assert yanit.data["frame_counts"]["failed"] == 0


def test_kare_sayimlari_gercek_durumlari_yansitiyor(auth_client, mission_with_frames):
    kareler = list(Frame.objects.filter(mission=mission_with_frames).order_by("id"))
    Frame.objects.filter(pk=kareler[0].pk).update(status=Frame.Status.DONE)
    Frame.objects.filter(pk=kareler[1].pk).update(status=Frame.Status.FAILED)

    yanit = auth_client.get(reverse("mission-detail", args=[mission_with_frames.id]))
    sayimlar = yanit.data["frame_counts"]

    assert sayimlar["done"] == 1
    assert sayimlar["failed"] == 1
    assert sayimlar["pending"] == 1
    assert yanit.data["frame_count"] == 3


def test_gorev_listesi_de_sayim_ve_son_kosu_tasiyor(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    tarama_baslat(auth_client, mission_with_frames, model_version)

    liste = auth_client.get(reverse("mission-list"))
    gorev = liste.data["results"][0]

    assert gorev["frame_count"] == 3
    assert gorev["latest_run"]["model_version_name"] == model_version.name
    assert gorev["latest_run"]["status"] == InferenceRun.Status.DONE


def test_kosusu_olmayan_gorevde_latest_run_null(auth_client, mission_with_frames):
    yanit = auth_client.get(reverse("mission-detail", args=[mission_with_frames.id]))
    assert yanit.data["latest_run"] is None


def test_sayimlar_baska_gorevin_karelerini_katmiyor(
    auth_client, user, mission_with_frames, make_image
):
    from core.services import ingest_frame

    digeri = Mission.objects.create(name="Ikinci gorev", created_by=user)
    ingest_frame(digeri, make_image(name="tek.jpg", color=(9, 9, 9)))

    yanit = auth_client.get(reverse("mission-detail", args=[digeri.id]))
    assert yanit.data["frame_count"] == 1


# --- Kosu listesi ----------------------------------------------------------


def test_gorev_kosulari_listeleniyor(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    ilk = tarama_baslat(auth_client, mission_with_frames, model_version)
    ikinci = tarama_baslat(auth_client, mission_with_frames, model_version)

    liste = auth_client.get(reverse("mission-runs", args=[mission_with_frames.id]))

    assert liste.status_code == 200
    kimlikler = [k["id"] for k in liste.data["results"]]
    # Yeniden eskiye: en son baslatilan kosu basta.
    assert kimlikler[0] == ikinci.data["run_id"]
    assert ilk.data["run_id"] in kimlikler


def test_kosu_listesi_ilerleme_alanlarini_tasiyor(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    tarama_baslat(auth_client, mission_with_frames, model_version)
    liste = auth_client.get(reverse("mission-runs", args=[mission_with_frames.id]))
    kosu = liste.data["results"][0]

    for alan in ("status", "frames_total", "frames_done", "frames_failed",
                 "conf_threshold", "model_version_name"):
        assert alan in kosu, f"{alan} alani kosu listesinde yok"


def test_baskasinin_gorevinin_kosu_listesi_404(
    api_client, other_user, mission_with_frames
):
    api_client.force_authenticate(user=other_user)
    yanit = api_client.get(reverse("mission-runs", args=[mission_with_frames.id]))
    assert yanit.status_code == 404


def test_kosu_listesi_kimlik_dogrulama_istiyor(api_client, mission_with_frames):
    yanit = api_client.get(reverse("mission-runs", args=[mission_with_frames.id]))
    assert yanit.status_code in (401, 403)


# --- Goruntu ucu -----------------------------------------------------------


def test_kare_goruntusu_kimlik_dogrulamayla_geliyor(auth_client, mission_with_frames):
    kare = Frame.objects.filter(mission=mission_with_frames).first()
    yanit = auth_client.get(reverse("frame-image", args=[kare.id]))

    assert yanit.status_code == 200
    assert yanit["Content-Type"] == "image/jpeg"
    assert yanit["X-Content-Type-Options"] == "nosniff"
    assert b"".join(yanit.streaming_content).startswith(b"\xff\xd8")  # JPEG imzasi


def test_kare_goruntusu_kimliksiz_reddediliyor(api_client, mission_with_frames):
    kare = Frame.objects.filter(mission=mission_with_frames).first()
    yanit = api_client.get(reverse("frame-image", args=[kare.id]))
    assert yanit.status_code in (401, 403)


def test_baskasinin_karesinin_goruntusu_404(
    api_client, other_user, mission_with_frames
):
    """Sahiplik suzgeci: 403 degil 404 -- karenin VARLIGI bile sizmasin."""
    kare = Frame.objects.filter(mission=mission_with_frames).first()
    api_client.force_authenticate(user=other_user)
    yanit = api_client.get(reverse("frame-image", args=[kare.id]))
    assert yanit.status_code == 404


def test_olmayan_kare_goruntusu_404(auth_client):
    yanit = auth_client.get(reverse("frame-image", args=[999999]))
    assert yanit.status_code == 404


def test_dosyasi_silinmis_kare_500_degil_404(auth_client, mission_with_frames):
    import os

    kare = Frame.objects.filter(mission=mission_with_frames).first()
    os.remove(kare.image.path)

    yanit = auth_client.get(reverse("frame-image", args=[kare.id]))
    assert yanit.status_code == 404
