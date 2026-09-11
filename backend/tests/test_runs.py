"""Tarama boru hatti entegrasyon testleri.

Gorevler CELERY_TASK_ALWAYS_EAGER ile senkron kosar: Redis veya ayakta bir isci
gerekmez, ama tasks.py'nin gercek kodu calisir.

transaction=True KULLANMIYORUZ: o kip her testten sonra tablolari bosaltir ve
veri migration'inin yazdigi fake-v0 kaydi geri gelmez. Bunun yerine normal
django_db (geri sarilan islem) + django_capture_on_commit_callbacks: gorevi
kuyruga atan transaction.on_commit geri cagirmasi boylece yine calisir.
"""
import pytest
from django.urls import reverse

from core.models import Detection, Frame, InferenceRun, Mission
from core.tasks import process_frame

pytestmark = pytest.mark.django_db


@pytest.fixture
def tarama_baslat(django_capture_on_commit_callbacks):
    """Taramayi baslatir ve on_commit geri cagirmasini gercekten calistirir."""

    def _baslat(client, mission, model_version, **ekstra):
        govde = {"model_version_id": model_version.id}
        govde.update(ekstra)
        with django_capture_on_commit_callbacks(execute=True):
            yanit = client.post(
                reverse("mission-runs", args=[mission.id]), govde, format="json"
            )
        return yanit

    return _baslat


def test_tarama_baslatmak_202_ve_run_id_donuyor(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    yanit = tarama_baslat(auth_client, mission_with_frames, model_version)
    assert yanit.status_code == 202
    assert "run_id" in yanit.data
    assert yanit.data["frames_total"] == 3


def test_tarama_bitince_run_done_ve_frames_done_dogru(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    yanit = tarama_baslat(auth_client, mission_with_frames, model_version)
    run = InferenceRun.objects.get(pk=yanit.data["run_id"])

    assert run.status == InferenceRun.Status.DONE
    assert run.frames_total == 3
    assert run.frames_done == 3
    assert run.frames_failed == 0
    assert run.finished_at is not None
    assert set(
        Frame.objects.filter(mission=mission_with_frames).values_list("status", flat=True)
    ) == {Frame.Status.DONE}


def test_detection_kayitlari_olusuyor_ve_koordinatlar_sinir_icinde(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    yanit = tarama_baslat(auth_client, mission_with_frames, model_version)
    run = InferenceRun.objects.get(pk=yanit.data["run_id"])

    tespitler = list(Detection.objects.filter(inference_run=run).select_related("frame"))
    assert tespitler, "Sahte dedektor hic kutu uretmedi; tohum ayari bozuk olabilir."

    for tespit in tespitler:
        kare = tespit.frame
        assert 0 <= tespit.x1 < tespit.x2 <= kare.width
        assert 0 <= tespit.y1 < tespit.y2 <= kare.height
        assert 0.0 <= tespit.score <= 1.0


def test_ayni_gorevi_iki_kez_calistirmak_tespitleri_ikiye_katlamiyor(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    yanit = tarama_baslat(auth_client, mission_with_frames, model_version)
    run_id = yanit.data["run_id"]

    once = Detection.objects.filter(inference_run_id=run_id).count()
    onceki_frames_done = InferenceRun.objects.get(pk=run_id).frames_done

    # acks_late acikken Celery bir gorevi yeniden dagitabilir. Aynisini taklit
    # ediyoruz: kare zaten done, gorev tekrar calisiyor.
    for kare in Frame.objects.filter(mission=mission_with_frames):
        process_frame.apply(args=(run_id, kare.id)).get()

    assert Detection.objects.filter(inference_run_id=run_id).count() == once
    assert InferenceRun.objects.get(pk=run_id).frames_done == onceki_frames_done


def test_yeniden_islenen_kare_tespitleri_yerine_koyuyor(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    """Kare done degilse gorev isi yapar, ama EKLEMEZ -- sil sonra yaz."""
    yanit = tarama_baslat(auth_client, mission_with_frames, model_version)
    run_id = yanit.data["run_id"]
    kare = Frame.objects.filter(mission=mission_with_frames).first()
    once = Detection.objects.filter(inference_run_id=run_id, frame=kare).count()

    # Kareyi "yarim kalmis" duruma dusur, sonra gorevi tekrar calistir.
    Frame.objects.filter(pk=kare.pk).update(status=Frame.Status.PROCESSING)
    process_frame.apply(args=(run_id, kare.id)).get()

    # Dedektor sha256'dan tohumlu, ayni kutulari uretir; sayi degismemeli.
    assert Detection.objects.filter(inference_run_id=run_id, frame=kare).count() == once


def test_baskasinin_gorevinde_tarama_baslatmak_404(
    api_client, other_user, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    api_client.force_authenticate(user=other_user)
    yanit = tarama_baslat(api_client, mission_with_frames, model_version)
    assert yanit.status_code == 404
    assert not InferenceRun.objects.filter(mission=mission_with_frames).exists()


def test_baskasinin_kosusunu_gormek_404(
    api_client, auth_client, other_user, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    yanit = tarama_baslat(auth_client, mission_with_frames, model_version)
    run_id = yanit.data["run_id"]

    api_client.force_authenticate(user=other_user)
    assert api_client.get(reverse("run-detail", args=[run_id])).status_code == 404
    assert api_client.get(reverse("run-detections", args=[run_id])).status_code == 404


def test_karesi_olmayan_gorevde_tarama_baslatmak_400(
    auth_client, user, model_version, celery_eager, tarama_baslat
):
    bos_gorev = Mission.objects.create(name="Bos gorev", created_by=user)
    yanit = tarama_baslat(auth_client, bos_gorev, model_version)
    assert yanit.status_code == 400
    assert not InferenceRun.objects.filter(mission=bos_gorev).exists()


def test_kimlik_dogrulamasiz_erisim_reddediliyor(
    api_client, mission_with_frames, model_version
):
    yollar = [
        reverse("mission-runs", args=[mission_with_frames.id]),
        reverse("run-detail", args=[1]),
        reverse("run-detections", args=[1]),
        reverse("model-list"),
    ]
    for yol in yollar:
        assert api_client.get(yol).status_code in (401, 403)


def test_detections_ucu_skora_gore_azalan_sirali(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    yanit = tarama_baslat(
        auth_client, mission_with_frames, model_version, conf_threshold=0.0
    )
    run_id = yanit.data["run_id"]

    liste = auth_client.get(reverse("run-detections", args=[run_id]))
    assert liste.status_code == 200
    skorlar = [t["score"] for t in liste.data["results"]]
    assert skorlar == sorted(skorlar, reverse=True)


def test_run_durum_ucu_ilerlemeyi_donuyor(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    yanit = tarama_baslat(auth_client, mission_with_frames, model_version)
    durum = auth_client.get(reverse("run-detail", args=[yanit.data["run_id"]]))

    assert durum.status_code == 200
    assert durum.data["status"] == InferenceRun.Status.DONE
    assert durum.data["frames_total"] == 3
    assert durum.data["frames_done"] == 3
    assert durum.data["frames_failed"] == 0
    assert durum.data["started_at"] and durum.data["finished_at"]


def test_esik_kayda_pisirilmiyor_okuma_aninda_uygulaniyor(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    """Yuksek conf_threshold ile kosulsa bile DUSUK skorlu kutular SAKLANIR."""
    yanit = tarama_baslat(
        auth_client, mission_with_frames, model_version, conf_threshold=0.9
    )
    run_id = yanit.data["run_id"]

    # Kayitta taban DETECTION_STORE_FLOOR; 0.9'un altinda kutu bulunmali.
    assert Detection.objects.filter(inference_run_id=run_id, score__lt=0.9).exists()

    # Varsayilan okuma kosunun esigini uygular: hepsi >= 0.9.
    varsayilan = auth_client.get(reverse("run-detections", args=[run_id]))
    assert all(t["score"] >= 0.9 for t in varsayilan.data["results"])

    # min_score ile ayni kosudan daha dusuk esik sorulabiliyor -- yeniden
    # taramaya gerek yok.
    dusuk = auth_client.get(
        reverse("run-detections", args=[run_id]), {"min_score": 0.05}
    )
    assert dusuk.data["count"] > varsayilan.data["count"]


def test_detections_frame_id_ile_filtreleniyor(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    yanit = tarama_baslat(
        auth_client, mission_with_frames, model_version, conf_threshold=0.0
    )
    run_id = yanit.data["run_id"]
    kare = Frame.objects.filter(mission=mission_with_frames).first()

    liste = auth_client.get(
        reverse("run-detections", args=[run_id]), {"frame_id": kare.id}
    )
    assert liste.status_code == 200
    assert {t["frame"] for t in liste.data["results"]} <= {kare.id}


def test_kare_basarisiz_olursa_kosu_yine_done_ama_sayac_gorunur(
    auth_client, mission_with_frames, model_version, celery_eager, monkeypatch, tarama_baslat
):
    """Bir kare patlasa bile chord tamamlanmali, kosu done olmali."""
    import core.tasks as tasks

    patlayacak = Frame.objects.filter(mission=mission_with_frames).first()
    gercek = tasks._process_frame_inner

    def sahte(run_id, frame_id):
        if frame_id == patlayacak.id:
            raise RuntimeError("dedektor coktu")
        return gercek(run_id, frame_id)

    monkeypatch.setattr(tasks, "_process_frame_inner", sahte)

    yanit = tarama_baslat(auth_client, mission_with_frames, model_version)
    run = InferenceRun.objects.get(pk=yanit.data["run_id"])

    assert run.status == InferenceRun.Status.DONE
    assert run.frames_failed == 1
    assert run.frames_done == 2
    assert Frame.objects.get(pk=patlayacak.pk).status == Frame.Status.FAILED


def test_models_ucu_fake_v0_donuyor(auth_client, model_version):
    yanit = auth_client.get(reverse("model-list"))
    assert yanit.status_code == 200
    assert "fake-v0" in [m["name"] for m in yanit.data["results"]]


def test_gecersiz_kosu_parametreleri_400(
    auth_client, mission_with_frames, model_version, celery_eager, tarama_baslat
):
    yanit = tarama_baslat(
        auth_client, mission_with_frames, model_version, conf_threshold=1.5
    )
    assert yanit.status_code == 400
