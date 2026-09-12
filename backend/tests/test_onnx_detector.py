"""Gercek ONNX dedektorunun boru hattina baglanmasinin testleri.

Iki katman test edilir:
  1. Dedektorun kendisi (on isleme, cozme, oturum paylasimi) -- gercek model
     dosyasi gerektirenler ONNX_MODEL_PATH yoksa atlanir.
  2. Celery gorevi uzerinden uctan uca davranis -- burada model dosyasi
     gerekmez, dedektor sahte bir oturumla degistirilir. Boylece "gercek
     dedektor secildi mi, koordinat tasindi mi, taban uygulandi mi, tekrar
     calisirsa kopya olusuyor mu" sorulari model olmadan da yanitlanir.
"""
import numpy as np
import pytest
from django.conf import settings
from django.urls import reverse

from core import detector as detector_modulu
from core.models import Detection, Frame, InferenceRun, ModelVersion
from core.onnx_detector import (
    OnnxDedektor,
    ModelYuklenemedi,
    _mektup_kutusu,
    paylasilan_dedektor,
)
from core.tasks import process_frame

pytestmark = pytest.mark.django_db

MODEL_YOLU = settings.ONNX_MODEL_PATH
model_gerekir = pytest.mark.skipif(
    not MODEL_YOLU or not __import__("pathlib").Path(MODEL_YOLU).is_file(),
    reason="ONNX_MODEL_PATH bos veya dosya yok",
)


@pytest.fixture
def onnx_model_version(db):
    return ModelVersion.objects.get(name="model512-onnx")


class SahteOturum:
    """ONNX Runtime oturumunun yerine gecen kayit tutucu.

    Kendisine verilen tensoru saklar ve sabit bir cikti dondurur; boylece on
    isleme ve cozme, model dosyasi olmadan olculebilir."""

    def __init__(self, cikti=None):
        self.cagrilar = []
        self.cikti = cikti

    def run(self, cikti_adlari, girdi):
        self.cagrilar.append(next(iter(girdi.values())))
        if self.cikti is None:
            # (1, 5, aday): tek aday, giris karesinin ortasinda 200x200 kutu,
            # skor 0.9. Merkez seciliyor ki kucuk karolarda mektup kutusu
            # dolgusuna dusup sifir alana inmesin.
            return [np.array([[[256.0], [256.0], [200.0], [200.0], [0.9]]], dtype=np.float32)]
        return [self.cikti]


def sahte_dedektor(cikti=None, giris_boyu=512):
    """Oturumu sahte olan, geri kalani gercek olan bir OnnxDedektor uretir."""
    dedektor = OnnxDedektor.__new__(OnnxDedektor)
    dedektor.oturum = SahteOturum(cikti)
    dedektor.girdi_adi = "images"
    dedektor.girdi_sekli = [1, 3, giris_boyu, giris_boyu]
    dedektor.cikti_adlari = ["output0"]
    dedektor.conf_esigi = settings.DETECTION_STORE_FLOOR
    dedektor.sinif_adlari = {0: "human"}
    dedektor.giris_boyu = giris_boyu
    return dedektor


# --- Model yolu ve yukleme hatasi ---------------------------------------------


def test_model_yolu_ayardan_okunuyor(settings, onnx_model_version, monkeypatch):
    """get_detector, model yolunu kodda sabit tutmaz; ayardan alir."""
    settings.ONNX_MODEL_PATH = "/baska/bir/yol/model.onnx"
    kullanilan = {}

    def sahte_paylasilan(yol, conf, **kwargs):
        kullanilan["yol"] = yol
        kullanilan["conf"] = conf
        return sahte_dedektor()

    monkeypatch.setattr("core.onnx_detector.paylasilan_dedektor", sahte_paylasilan)
    detector_modulu.get_detector(onnx_model_version, frame_sha256="abc")

    assert kullanilan["yol"] == "/baska/bir/yol/model.onnx"
    assert kullanilan["conf"] == settings.DETECTION_STORE_FLOOR


def test_model_yolu_bos_ise_acik_hata(settings, onnx_model_version):
    """Ayar bos birakilirsa sessizce sahte dedektore dusulmez."""
    settings.ONNX_MODEL_PATH = ""
    with pytest.raises(ModelYuklenemedi):
        detector_modulu.get_detector(onnx_model_version, frame_sha256="abc")


def test_model_dosyasi_yoksa_acik_hata(settings, onnx_model_version, tmp_path):
    """Var olmayan dosya icin hata mesaji yolu icermeli."""
    settings.ONNX_MODEL_PATH = str(tmp_path / "olmayan.onnx")
    with pytest.raises(ModelYuklenemedi) as hata:
        detector_modulu.get_detector(onnx_model_version, frame_sha256="abc")
    assert "olmayan.onnx" in str(hata.value)


def test_sahte_cerceve_sahte_dedektor_kaliyor(model_version):
    """fake-v0 kosulari gercek modele gecmemeli."""
    dedektor = detector_modulu.get_detector(model_version, frame_sha256="abc")
    assert isinstance(dedektor, detector_modulu.FakeDetector)


# --- On isleme ve cozme -------------------------------------------------------


def test_girdi_sekli_ve_veri_turu_dogru():
    """Modele verilen tensor (1, 3, 512, 512) float32 olmali."""
    dedektor = sahte_dedektor()
    dedektor.karo_tahmin_et(np.zeros((512, 512, 3), dtype=np.uint8))
    tensor = dedektor.oturum.cagrilar[0]
    assert tensor.shape == (1, 3, 512, 512)
    assert tensor.dtype == np.float32


def test_kanal_sirasi_ve_normalizasyon_olcum_ile_ayni():
    """Girdi RGB sirasini korur ve 0-1 araligina bolunur (A asamasiyla ayni)."""
    karo = np.zeros((512, 512, 3), dtype=np.uint8)
    karo[:, :, 0] = 255   # R
    karo[:, :, 1] = 128   # G
    karo[:, :, 2] = 0     # B

    dedektor = sahte_dedektor()
    dedektor.karo_tahmin_et(karo)
    tensor = dedektor.oturum.cagrilar[0]

    assert tensor[0, 0].max() == pytest.approx(1.0)
    assert tensor[0, 1].max() == pytest.approx(128 / 255)
    assert tensor[0, 2].max() == pytest.approx(0.0)


def test_onnx_ciktisi_kutu_bicimine_ceviriliyor():
    """(cx, cy, g, y) cikti (x1, y1, x2, y2) kutusuna donusmeli."""
    dedektor = sahte_dedektor()
    kutular = dedektor.karo_tahmin_et(np.zeros((512, 512, 3), dtype=np.uint8))
    assert len(kutular) == 1
    x1, y1, x2, y2, skor = kutular[0]
    assert (x1, y1, x2, y2) == pytest.approx((156.0, 156.0, 356.0, 356.0))
    assert skor == pytest.approx(0.9)


def test_esik_altindaki_aday_donmuyor():
    """Guven esiginin altindaki aday kutu uretilmemeli."""
    dusuk = np.array([[[256.0], [256.0], [200.0], [200.0], [0.01]]], dtype=np.float32)
    dedektor = sahte_dedektor(cikti=dusuk)
    assert dedektor.karo_tahmin_et(np.zeros((512, 512, 3), dtype=np.uint8)) == []


def test_kucuk_karo_mektup_kutusu_ile_geri_olcekleniyor():
    """Giris boyundan kucuk karoda kutular karo duzlemine geri tasinmali."""
    tuval, olcek, (dolgu_x, dolgu_y) = _mektup_kutusu(
        np.zeros((256, 256, 3), dtype=np.uint8), 512
    )
    assert tuval.shape == (512, 512, 3)
    assert olcek == pytest.approx(2.0)
    assert (dolgu_x, dolgu_y) == pytest.approx((0.0, 0.0))

    dedektor = sahte_dedektor()
    for x1, y1, x2, y2, _ in dedektor.karo_tahmin_et(np.zeros((256, 256, 3), dtype=np.uint8)):
        assert 0 <= x1 < x2 <= 256
        assert 0 <= y1 < y2 <= 256


@model_gerekir
def test_gercek_model_kimligi_dogrulaniyor():
    """Gercek dosyada sinif kumesi ve giris boyu beklenen degerde olmali."""
    dedektor = OnnxDedektor(MODEL_YOLU, settings.DETECTION_STORE_FLOOR)
    assert dedektor.sinif_adlari == {0: "human"}
    assert dedektor.giris_boyu == 512


@model_gerekir
def test_oturum_her_karo_icin_yeniden_olusturulmuyor():
    """Ayni model yolu ve esik icin surec basina tek oturum tutulmali."""
    bir = paylasilan_dedektor(MODEL_YOLU, settings.DETECTION_STORE_FLOOR)
    iki = paylasilan_dedektor(MODEL_YOLU, settings.DETECTION_STORE_FLOOR)
    assert bir is iki and bir.oturum is iki.oturum


def test_gorev_boyunca_tek_dedektor_kuruluyor(
    settings, onnx_model_version, mission_with_frames, monkeypatch
):
    """Kare islenirken dedektor karo basina degil, kare basina bir kez kurulur."""
    settings.ONNX_MODEL_PATH = "/models/sahte.onnx"
    kurulum = []
    dedektor = sahte_dedektor()
    monkeypatch.setattr(
        "core.onnx_detector.paylasilan_dedektor",
        lambda *a, **k: (kurulum.append(a) or dedektor),
    )

    run = kosu_olustur(mission_with_frames, onnx_model_version)
    frame = mission_with_frames.frames.first()
    process_frame(run.id, frame.id)

    assert len(kurulum) == 1
    assert len(dedektor.oturum.cagrilar) >= 1


# --- Gorev uzerinden uctan uca ------------------------------------------------


def kosu_olustur(mission, model_version, conf=0.30, iou=0.3):
    return InferenceRun.objects.create(
        mission=mission,
        model_version=model_version,
        conf_threshold=conf,
        iou_threshold=iou,
        tile_size=model_version.tile_size,
        overlap_ratio=model_version.overlap_ratio,
        status=InferenceRun.Status.RUNNING,
    )


@pytest.fixture
def onnx_kosusu(settings, onnx_model_version, mission_with_frames, monkeypatch):
    """Gercek dedektor secilir ama oturumu sahtedir: model dosyasi gerekmez."""
    settings.ONNX_MODEL_PATH = "/models/sahte.onnx"
    dedektor = sahte_dedektor()
    monkeypatch.setattr(
        "core.onnx_detector.paylasilan_dedektor", lambda *a, **k: dedektor
    )
    run = kosu_olustur(mission_with_frames, onnx_model_version)
    return run, mission_with_frames.frames.first(), dedektor


def test_tespitler_tam_goruntu_koordinatina_tasiniyor(onnx_kosusu):
    """Karo duzlemindeki kutu, karo kosesi eklenerek saklanmali."""
    run, frame, _ = onnx_kosusu
    process_frame(run.id, frame.id)

    tespitler = list(Detection.objects.filter(inference_run=run, frame=frame))
    assert tespitler
    for tespit in tespitler:
        assert 0 <= tespit.x1 < tespit.x2 <= frame.width
        assert 0 <= tespit.y1 < tespit.y2 <= frame.height


def test_skor_ve_karo_indeksi_saklaniyor(onnx_kosusu):
    """score, tile_row ve tile_col alanlari doldurulmali."""
    run, frame, _ = onnx_kosusu
    process_frame(run.id, frame.id)

    tespit = Detection.objects.filter(inference_run=run, frame=frame).first()
    assert tespit is not None
    assert tespit.score == pytest.approx(0.9)
    assert tespit.tile_row is not None and tespit.tile_col is not None


def test_depolama_tabani_altindaki_tespit_saklanmiyor(
    settings, onnx_model_version, mission_with_frames, monkeypatch
):
    """DETECTION_STORE_FLOOR altindaki skor veritabanina yazilmamali."""
    settings.ONNX_MODEL_PATH = "/models/sahte.onnx"
    dedektor = sahte_dedektor()
    # Dedektor esigin altinda bir kutu dondurse bile gorev onu yazmamali.
    monkeypatch.setattr(
        dedektor, "karo_tahmin_et", lambda karo: [(1.0, 1.0, 5.0, 5.0, 0.01)]
    )
    monkeypatch.setattr(
        "core.onnx_detector.paylasilan_dedektor", lambda *a, **k: dedektor
    )

    run = kosu_olustur(mission_with_frames, onnx_model_version)
    frame = mission_with_frames.frames.first()
    process_frame(run.id, frame.id)

    assert Detection.objects.filter(inference_run=run, frame=frame).count() == 0
    assert Frame.objects.get(pk=frame.id).status == Frame.Status.DONE


def test_basarili_gorev_frame_done_yapiyor(onnx_kosusu):
    """Gercek dedektorle biten kare done olmali."""
    run, frame, _ = onnx_kosusu
    sonuc = process_frame(run.id, frame.id)
    assert sonuc["status"] == "done"
    assert Frame.objects.get(pk=frame.id).status == Frame.Status.DONE


def test_ayni_kare_tekrar_islenirse_kopya_tespit_olusmuyor(onnx_kosusu):
    """Yeniden dagitilan gorev tespitleri ikiye katlamamali."""
    run, frame, _ = onnx_kosusu
    process_frame(run.id, frame.id)
    ilk = Detection.objects.filter(inference_run=run, frame=frame).count()

    Frame.objects.filter(pk=frame.id).update(status=Frame.Status.QUEUED)
    process_frame(run.id, frame.id)

    assert Detection.objects.filter(inference_run=run, frame=frame).count() == ilk


def test_onnx_hatasinda_sahte_dedektore_gecilmiyor(
    settings, onnx_model_version, mission_with_frames, tmp_path
):
    """Model yuklenemezse kare failed olur; sahte kutular uretilmez."""
    settings.ONNX_MODEL_PATH = str(tmp_path / "yok.onnx")
    run = kosu_olustur(mission_with_frames, onnx_model_version)
    frame = mission_with_frames.frames.first()

    # .apply(): gorev eager kipte kosar, yani yeniden deneme dongusune girmeden
    # hata yolu calisir. Projenin diger gorev testleri de boyle cagiriyor.
    sonuc = process_frame.apply(args=(run.id, frame.id)).get()

    assert sonuc["status"] == "failed"
    assert Frame.objects.get(pk=frame.id).status == Frame.Status.FAILED
    assert Detection.objects.filter(inference_run=run, frame=frame).count() == 0
    assert InferenceRun.objects.get(pk=run.id).frames_failed == 1


def test_onnx_model_surumu_ucdan_secilebiliyor(
    auth_client, mission_with_frames, onnx_model_version, celery_eager,
    settings, monkeypatch, django_capture_on_commit_callbacks
):
    """Kosu, gercek model surumuyle uctan baslatilabilmeli."""
    settings.ONNX_MODEL_PATH = "/models/sahte.onnx"
    monkeypatch.setattr(
        "core.onnx_detector.paylasilan_dedektor", lambda *a, **k: sahte_dedektor()
    )

    with django_capture_on_commit_callbacks(execute=True):
        yanit = auth_client.post(
            reverse("mission-runs", args=[mission_with_frames.id]),
            {"model_version_id": onnx_model_version.id},
            format="json",
        )

    assert yanit.status_code == 202
    run = InferenceRun.objects.get(pk=yanit.data["run_id"])
    assert run.status == InferenceRun.Status.DONE
    assert run.frames_done == 3
    assert run.frames_failed == 0
