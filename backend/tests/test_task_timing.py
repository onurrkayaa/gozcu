"""Asama bazinda sure olcumunun testleri.

Olculen sey gorevin kendi ic zamanlamasi: kayit ancak TASK_TIMING_LOG ayari
doluyken yazilir, sureler monoton saatten gelir ve soguk baslangic ayri
isaretlenir. Gercek model dosyasi gerekmez; dedektor sahte bir oturumla
degistirilir.
"""
import json

import numpy as np
import pytest
from django.conf import settings

from core import tasks
from core.models import Frame, InferenceRun, ModelVersion
from core.onnx_detector import OnnxDedektor
from core.tasks import _zamanlama_yaz, process_frame

pytestmark = pytest.mark.django_db

SURE_ALANLARI = (
    "kuyruk_bekleme", "goruntu_okuma", "karolama", "onnx_cikarim",
    "nms_koordinat", "db_yazma", "frame_toplam", "uctan_uca_sure",
)


class SahteOturum:
    def __init__(self):
        self.cagrilar = 0

    def run(self, cikti_adlari, girdi):
        self.cagrilar += 1
        return [np.array([[[256.0], [256.0], [200.0], [200.0], [0.9]]], dtype=np.float32)]


def sahte_dedektor():
    """Gercek OnnxDedektor'un oturumu disindaki her seyi: sayaclar dahil."""
    dedektor = OnnxDedektor.__new__(OnnxDedektor)
    dedektor.oturum = SahteOturum()
    dedektor.girdi_adi = "images"
    dedektor.girdi_sekli = [1, 3, 512, 512]
    dedektor.cikti_adlari = ["output0"]
    dedektor.conf_esigi = settings.DETECTION_STORE_FLOOR
    dedektor.sinif_adlari = {0: "human"}
    dedektor.giris_boyu = 512
    dedektor.kurulum_suresi = 0.25
    dedektor.kare_sayisi = 0
    dedektor.sayaclar = {"goruntu_okuma": 0.0, "cikarim": 0.0, "son_islem": 0.0}
    return dedektor


@pytest.fixture
def onnx_model_version(db):
    return ModelVersion.objects.get(name="model512-onnx")


@pytest.fixture
def zamanlama_kosusu(settings, tmp_path, onnx_model_version, mission_with_frames, monkeypatch):
    """Gercek dedektor secilir, oturumu sahtedir; zamanlama kaydi acik."""
    settings.ONNX_MODEL_PATH = "/models/sahte.onnx"
    settings.TASK_TIMING_LOG = str(tmp_path / "zamanlama.jsonl")
    dedektor = sahte_dedektor()
    monkeypatch.setattr("core.onnx_detector.paylasilan_dedektor", lambda *a, **k: dedektor)

    kosu = InferenceRun.objects.create(
        mission=mission_with_frames,
        model_version=onnx_model_version,
        conf_threshold=0.30,
        iou_threshold=0.3,
        tile_size=onnx_model_version.tile_size,
        overlap_ratio=onnx_model_version.overlap_ratio,
        status=InferenceRun.Status.RUNNING,
    )
    return kosu, list(mission_with_frames.frames.order_by("id")), dedektor, settings.TASK_TIMING_LOG


def kayitlari_oku(yol):
    return [json.loads(s) for s in open(yol, encoding="utf-8").read().splitlines() if s.strip()]


# --- Ayarin acip kapatmasi ----------------------------------------------------


def test_ayar_bossa_kayit_yazilmiyor(settings, tmp_path):
    """Olcum kapaliyken hicbir dosya olusmamali."""
    yol = tmp_path / "olmamali.jsonl"
    settings.TASK_TIMING_LOG = ""
    _zamanlama_yaz({"frame_id": 1})
    assert not yol.exists()


def test_ayar_doluyken_json_satiri_ekleniyor(settings, tmp_path):
    """Her cagri tek bir JSON satiri eklemeli."""
    yol = tmp_path / "zamanlama.jsonl"
    settings.TASK_TIMING_LOG = str(yol)
    _zamanlama_yaz({"frame_id": 1, "frame_toplam": 1.5})
    _zamanlama_yaz({"frame_id": 2, "frame_toplam": 2.5})

    kayitlar = kayitlari_oku(yol)
    assert [k["frame_id"] for k in kayitlar] == [1, 2]


def test_yazilamayan_kayit_gorevi_bozmuyor(settings, tmp_path):
    """Olcum kaydi uretimi durdurmamali: yazilamazsa sessizce gecilir."""
    settings.TASK_TIMING_LOG = str(tmp_path / "olmayan_klasor" / "z.jsonl")
    _zamanlama_yaz({"frame_id": 1})  # hata yukseltmemeli


# --- Gorev uzerinden olcum ----------------------------------------------------


def test_butun_asama_sureleri_yaziliyor_ve_negatif_degil(zamanlama_kosusu):
    """Her sure alani kayitta bulunmali ve monoton saatten geldigi icin >= 0 olmali."""
    kosu, kareler, _, yol = zamanlama_kosusu
    process_frame(kosu.id, kareler[0].id)

    kayit = kayitlari_oku(yol)[0]
    for alan in SURE_ALANLARI:
        assert alan in kayit, f"eksik alan: {alan}"
        assert kayit[alan] >= 0, f"negatif sure: {alan}"
    assert kayit["durum"] == "done"
    assert kayit["hata_sinifi"] == ""


def test_frame_toplam_asamalardan_kucuk_olmuyor(zamanlama_kosusu):
    """Kare toplami, icindeki asamalarin toplamindan kucuk olamaz."""
    kosu, kareler, _, yol = zamanlama_kosusu
    process_frame(kosu.id, kareler[0].id)

    kayit = kayitlari_oku(yol)[0]
    asamalar = sum(kayit[a] for a in ("goruntu_okuma", "karolama", "onnx_cikarim",
                                      "nms_koordinat", "db_yazma"))
    assert kayit["frame_toplam"] >= asamalar - 1e-6
    assert kayit["uctan_uca_sure"] >= kayit["frame_toplam"] - 1e-6


def test_soguk_baslangic_ayri_isaretleniyor(zamanlama_kosusu):
    """Ilk kare soguk baslangic, sonraki kareler degil."""
    kosu, kareler, _, yol = zamanlama_kosusu
    process_frame(kosu.id, kareler[0].id)
    process_frame(kosu.id, kareler[1].id)

    birinci, ikinci = kayitlari_oku(yol)
    assert birinci["soguk_baslangic"] is True
    assert birinci["oturum_kurulum_suresi"] > 0
    assert ikinci["soguk_baslangic"] is False
    assert ikinci["oturum_kurulum_suresi"] == 0.0


def test_onnx_session_kareler_arasinda_yeniden_kullaniliyor(zamanlama_kosusu):
    """Ayni oturum ikinci karede de kullanilmali; kare sayaci artmali."""
    kosu, kareler, dedektor, yol = zamanlama_kosusu
    process_frame(kosu.id, kareler[0].id)
    ilk_cagri = dedektor.oturum.cagrilar
    process_frame(kosu.id, kareler[1].id)

    assert dedektor.kare_sayisi == 2
    assert dedektor.oturum.cagrilar > ilk_cagri
    assert [k["surec_kare_sirasi"] for k in kayitlari_oku(yol)] == [1, 2]


def test_hatali_karede_hata_sinifi_yaziliyor(settings, tmp_path, onnx_model_version,
                                             mission_with_frames):
    """Model yuklenemezse kayit hata sinifiyla birlikte yazilmali."""
    settings.ONNX_MODEL_PATH = str(tmp_path / "yok.onnx")
    settings.TASK_TIMING_LOG = str(tmp_path / "zamanlama.jsonl")
    kosu = InferenceRun.objects.create(
        mission=mission_with_frames, model_version=onnx_model_version,
        conf_threshold=0.30, iou_threshold=0.3,
        tile_size=onnx_model_version.tile_size,
        overlap_ratio=onnx_model_version.overlap_ratio,
        status=InferenceRun.Status.RUNNING,
    )
    kare = mission_with_frames.frames.first()
    process_frame.apply(args=(kosu.id, kare.id)).get()

    kayit = kayitlari_oku(settings.TASK_TIMING_LOG)[0]
    assert kayit["durum"] == "failed"
    assert kayit["hata_sinifi"] == "ModelYuklenemedi"
    assert kayit["uctan_uca_sure"] >= 0
    assert Frame.objects.get(pk=kare.id).status == Frame.Status.FAILED


def test_sahte_dedektorde_olcum_uretimi_bozmuyor(settings, tmp_path, model_version,
                                                 mission_with_frames):
    """fake-v0 kosusunda da kayit yazilir; ONNX'e ozel alanlar sifir kalir."""
    settings.TASK_TIMING_LOG = str(tmp_path / "zamanlama.jsonl")
    kosu = InferenceRun.objects.create(
        mission=mission_with_frames, model_version=model_version,
        conf_threshold=0.30, iou_threshold=0.3,
        tile_size=model_version.tile_size, overlap_ratio=model_version.overlap_ratio,
        status=InferenceRun.Status.RUNNING,
    )
    kare = mission_with_frames.frames.first()
    process_frame(kosu.id, kare.id)

    kayit = kayitlari_oku(settings.TASK_TIMING_LOG)[0]
    assert kayit["durum"] == "done"
    assert kayit["onnx_cikarim"] == 0.0
    assert kayit["frame_toplam"] > 0
