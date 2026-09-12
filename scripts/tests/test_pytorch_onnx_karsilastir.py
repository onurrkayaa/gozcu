"""18_pytorch_onnx_karsilastir.py ve backend/core/onnx_detector.py testleri.

Tam olcum BURADA TEKRARLANMAZ: 157 goruntuluk kosu ana scriptin isidir. Testler
protokol okuma, fark/metrik uretimi ve dedektorun karo bazinda davranisiyla
sinirlidir. Gercek modeli gerektiren testler model yoksa atlanir (ONNX dosyasi
depoya girmez).
"""

import csv
import sys
from pathlib import Path

import pytest

PROJE_KOK = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIZIN = PROJE_KOK / "scripts"

sys.path.insert(0, str(SCRIPT_DIZIN))
sys.path.insert(0, str(PROJE_KOK / "backend"))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "pt_onnx", SCRIPT_DIZIN / "18_pytorch_onnx_karsilastir.py"
)
karsilastir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(karsilastir)

from core.onnx_detector import (  # noqa: E402
    KARO_ICI_NMS_IOU,
    ModelYuklenemedi,
    OnnxDedektor,
    paylasilan_dedektor,
)
from ortak import Kutu  # noqa: E402

ONNX_MODELI = PROJE_KOK / "agirliklar" / "model512_best.onnx"
model_gerekir = pytest.mark.skipif(
    not ONNX_MODELI.is_file(), reason="agirliklar/model512_best.onnx yerelde yok"
)


def olcum_csv_yaz(tmp_path: Path, esikler=(0.05, 0.3)) -> Path:
    """test_model512.csv bicimini taklit eden kucuk bir olcum dosyasi."""
    yol = tmp_path / "olcum.csv"
    basliklar = [
        "kaynak_onek", "conf_esigi", "goruntu_sayisi", "gercek_kutu",
        "dogru_bulunan_tp", "kacirilan_fn", "recall", "yanlis_pozitif_fp",
        "fp_goruntu_basina", "precision", "kosu_model", "kosu_bolum",
        "kosu_goruntu_sayisi", "kosu_karo_boyutu", "kosu_ortusme_orani",
        "kosu_iou_esigi", "kosu_cihaz",
    ]
    with yol.open("w", newline="", encoding="utf-8") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=basliklar)
        yazici.writeheader()
        for onek in ("ZRI", "TOPLAM"):
            for conf in esikler:
                yazici.writerow({
                    "kaynak_onek": onek, "conf_esigi": conf, "goruntu_sayisi": 157,
                    "gercek_kutu": 970, "dogru_bulunan_tp": 900, "kacirilan_fn": 70,
                    "recall": 0.9278, "yanlis_pozitif_fp": 2000,
                    "fp_goruntu_basina": 12.74, "precision": 0.3103,
                    "kosu_model": "agirliklar/model512_best.pt", "kosu_bolum": "test",
                    "kosu_goruntu_sayisi": 157, "kosu_karo_boyutu": 512,
                    "kosu_ortusme_orani": 0.2, "kosu_iou_esigi": 0.3, "kosu_cihaz": "cpu",
                })
    return yol


# --- Protokol okuma -----------------------------------------------------------


def test_protokol_csvden_okunuyor(tmp_path):
    """Karo, ortusme, IoU, cihaz ve esikler dosyadan gelmeli."""
    protokol = karsilastir.protokol_oku(olcum_csv_yaz(tmp_path))
    assert protokol["karo"] == 512
    assert protokol["ortusme"] == 0.2
    assert protokol["iou"] == 0.3
    assert protokol["cihaz"] == "cpu"
    assert protokol["esikler"] == [0.05, 0.3]
    assert protokol["model"].endswith("model512_best.pt")


def test_olculen_metrikler_yalnizca_toplam_satirini_aliyor(tmp_path):
    """Capraz kontrolun referansi TOPLAM satiridir, onek satirlari degil."""
    kayit = karsilastir.olculen_metrikler(olcum_csv_yaz(tmp_path))
    assert sorted(kayit) == [0.05, 0.3]
    assert all(s["kaynak_onek"] == "TOPLAM" for s in kayit.values())


def test_kaynak_hashi_uyusmazsa_duruluyor(tmp_path):
    """Model kimligi export kaydiyla uyusmuyorsa tahmin calistirilmadan durulur."""
    pt = tmp_path / "model.pt"
    onnx = tmp_path / "model.onnx"
    pt.write_bytes(b"pt-baytlari")
    onnx.write_bytes(b"onnx-baytlari")

    bilgi = tmp_path / "bilgi.csv"

    def bilgi_yaz(pt_hash, onnx_hash):
        with bilgi.open("w", newline="", encoding="utf-8") as dosya:
            yazici = csv.DictWriter(dosya, fieldnames=["kaynak_pt_sha256", "onnx_sha256"])
            yazici.writeheader()
            yazici.writerow({"kaynak_pt_sha256": pt_hash, "onnx_sha256": onnx_hash})

    dogru_pt = karsilastir.KIMLIK.dosya_sha256(pt)
    dogru_onnx = karsilastir.KIMLIK.dosya_sha256(onnx)

    bilgi_yaz(dogru_pt, dogru_onnx)
    assert karsilastir.kaynaklari_dogrula(pt, onnx, bilgi) == {
        "pt": dogru_pt, "onnx": dogru_onnx
    }

    bilgi_yaz(dogru_pt, "baska-bir-ozet")
    with pytest.raises(SystemExit):
        karsilastir.kaynaklari_dogrula(pt, onnx, bilgi)


# --- Fark ve metrik satirlari -------------------------------------------------


def test_fark_satirlari_uc_durumu_da_yaziyor(tmp_path):
    """Eslesen, yalniz PyTorch ve yalniz ONNX tahminleri ayri ayri kaydedilmeli."""
    yol = tmp_path / "goruntu.jpg"
    ortak_kutu_pt = Kutu(10, 10, 50, 50, 0.9)
    ortak_kutu_onnx = Kutu(10.5, 10, 50, 50, 0.88)
    pt = {yol: [ortak_kutu_pt, Kutu(200, 200, 240, 240, 0.4)]}
    onnx = {yol: [ortak_kutu_onnx, Kutu(400, 400, 440, 440, 0.3)]}

    satirlar = karsilastir.fark_satirlari(pt, onnx, 0.3, [yol])
    durumlar = [s["eslesme_durumu"] for s in satirlar]
    assert durumlar.count("eslesti") == 1
    assert durumlar.count("yalniz_pytorch") == 1
    assert durumlar.count("yalniz_onnx") == 1

    eslesen = next(s for s in satirlar if s["eslesme_durumu"] == "eslesti")
    assert eslesen["skor_mutlak_fark"] == pytest.approx(0.02, abs=1e-6)
    assert eslesen["x1_mutlak_fark"] == pytest.approx(0.5, abs=1e-6)
    assert eslesen["kutu_iou"] > 0.9


def test_metrik_satirlari_fark_sutunlarini_hesapliyor(tmp_path):
    """Fark sutunlari iki motorun olculen degerlerinden uretilmeli."""
    yol = tmp_path / "goruntu.jpg"
    gercekler = {yol: [Kutu(10, 10, 50, 50)]}
    tahminler = {
        "pytorch": {yol: [Kutu(10, 10, 50, 50, 0.9)]},
        "onnx": {yol: [Kutu(10, 10, 50, 50, 0.9), Kutu(300, 300, 340, 340, 0.8)]},
    }
    sureler = {m: {"toplam_sure": 1.0, "goruntu_basina_sure": 1.0} for m in ("pytorch", "onnx")}

    satir = karsilastir.metrik_satirlari(gercekler, tahminler, sureler, [0.5], 0.3)[0]
    assert satir["pytorch_tp"] == 1 and satir["onnx_tp"] == 1
    assert satir["fark_tp"] == 0
    assert satir["pytorch_fp"] == 0 and satir["onnx_fp"] == 1
    assert satir["fark_fp"] == 1
    assert satir["pytorch_toplam_tahmin"] == 1 and satir["onnx_toplam_tahmin"] == 2
    assert satir["fark_precision"] == pytest.approx(
        satir["onnx_precision"] - satir["pytorch_precision"], abs=1e-4)


def test_capraz_kontrol_ve_motor_esitligi_farki_bildiriyor():
    """Mevcut kayittan sapan alan UYUSMADI, motorlar arasi sapma FARKLI olmali."""
    metrik = {
        "conf_esigi": 0.05, "goruntu_sayisi": 157, "hedef_sayisi": 970,
        "pytorch_tp": 900, "pytorch_fn": 70, "pytorch_fp": 2000,
        "pytorch_recall": 0.9278, "pytorch_fp_goruntu_basina": 12.74,
        "pytorch_precision": 0.3103,
        "onnx_tp": 899, "onnx_fn": 71, "onnx_fp": 2000,
        "onnx_recall": 0.9268, "onnx_fp_goruntu_basina": 12.74,
        "onnx_precision": 0.3101,
    }
    kayit = {0.05: {
        "dogru_bulunan_tp": "900", "kacirilan_fn": "70", "yanlis_pozitif_fp": "2000",
        "recall": "0.9278", "fp_goruntu_basina": "12.74", "precision": "0.3103",
        "goruntu_sayisi": "157", "gercek_kutu": "970",
    }}
    assert all(s["sonuc"] == "UYUSTU" for s in karsilastir.capraz_kontrol([metrik], kayit))

    kayit[0.05]["dogru_bulunan_tp"] = "901"
    sapan = [s for s in karsilastir.capraz_kontrol([metrik], kayit) if s["sonuc"] == "UYUSMADI"]
    assert [s["alan"] for s in sapan] == ["pytorch_tp"]

    farkli = [s for s in karsilastir.motor_esitligi([metrik]) if s["sonuc"] == "FARKLI"]
    assert sorted(s["alan"] for s in farkli) == ["fn", "precision", "recall", "tp"]


# --- Paylasilan ONNX dedektoru ------------------------------------------------


def test_model_bulunamazsa_acik_hata(tmp_path):
    """Yanlis yol sessizce gecilmemeli."""
    with pytest.raises(ModelYuklenemedi) as hata:
        OnnxDedektor(tmp_path / "yok.onnx", 0.05)
    assert "yok.onnx" in str(hata.value)


@model_gerekir
def test_model_kimligi_ve_giris_boyu_okunuyor():
    """Sinif kumesi ve giris boyu model metadata'sindan dogrulanmali."""
    dedektor = OnnxDedektor(ONNX_MODELI, 0.05)
    assert dedektor.sinif_adlari == {0: "human"}
    assert dedektor.giris_boyu == 512
    assert dedektor.girdi_sekli == [1, 3, 512, 512]


@model_gerekir
def test_oturum_her_karo_icin_yeniden_acilmiyor():
    """Ayni model ve esik icin surec basina tek oturum tutulmali."""
    bir = paylasilan_dedektor(ONNX_MODELI, 0.05)
    iki = paylasilan_dedektor(ONNX_MODELI, 0.05)
    assert bir is iki
    assert bir.oturum is iki.oturum


@model_gerekir
def test_karo_tahmini_karo_sinirlari_icinde_kaliyor():
    """Kutular karo duzleminde ve esigin uzerinde donmeli."""
    import numpy as np

    dedektor = OnnxDedektor(ONNX_MODELI, 0.05)
    karo = np.zeros((512, 512, 3), dtype=np.uint8)
    kutular = dedektor.karo_tahmin_et(karo)
    assert isinstance(kutular, list)
    for x1, y1, x2, y2, skor in kutular:
        assert 0 <= x1 < x2 <= 512 and 0 <= y1 < y2 <= 512
        assert skor > 0.05


@model_gerekir
def test_kucuk_karo_mektup_kutusuyla_isleniyor():
    """Giris boyundan kucuk karo olceklenir ve kutular karo sinirinda kalir."""
    import numpy as np

    dedektor = OnnxDedektor(ONNX_MODELI, 0.05)
    kucuk = np.zeros((64, 48, 3), dtype=np.uint8)
    for x1, y1, x2, y2, _ in dedektor.karo_tahmin_et(kucuk):
        assert 0 <= x1 < x2 <= 48
        assert 0 <= y1 < y2 <= 64


def test_mektup_kutusu_tam_boyutta_kimlik_islemi():
    """Karo zaten giris boyutundaysa olcekleme ve dolgu yapilmamali."""
    import numpy as np

    from core.onnx_detector import _mektup_kutusu

    karo = np.zeros((512, 512, 3), dtype=np.uint8)
    tuval, olcek, dolgu = _mektup_kutusu(karo, 512)
    assert olcek == 1.0 and dolgu == (0.0, 0.0)
    assert tuval is karo

    kucuk = np.zeros((100, 50, 3), dtype=np.uint8)
    tuval, olcek, (dolgu_x, dolgu_y) = _mektup_kutusu(kucuk, 512)
    assert tuval.shape == (512, 512, 3)
    assert olcek == pytest.approx(5.12)
    assert dolgu_x == pytest.approx((512 - 256) / 2)
    assert dolgu_y == pytest.approx(0.0)


def test_karo_ici_nms_esigi_ultralytics_varsayilaniyla_ayni():
    """Karo ici NMS esigi olcum ve uretimde ayni sabitten gelmeli."""
    assert KARO_ICI_NMS_IOU == 0.7
