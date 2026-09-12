"""Kaynak goruntunun KARE BASINA BIR KEZ okunmasinin testleri.

Eski davranis: OnnxDedektor.detect her KARO icin goruntuyu diskten yeniden
aciyordu (4000x3000 goruntude 80 karo -> 80 acma). Bu testler yeni davranisi
sabitler: goruntu kare basina bir kez acilir, karolar ayni bellekteki
goruntuden kesilir ve BASKA HICBIR SEY degismez -- karo koordinatlari, tensor
bicimi, tespit kutulari ve zamanlama alanlarinin anlami ayni kalir.
"""
import numpy as np
import pytest
from django.conf import settings
from PIL import Image

from core.onnx_detector import OnnxDedektor
from core.tiling import karodan_global_koordinata, karolari_hesapla

GORUNTU_OLCU = (700, 500)
KARO = 256
ORTUSME = 0.2


class SayanOturum:
    """ONNX oturumunun yerine gecen, verilen tensorleri saklayan kayitci."""

    def __init__(self):
        self.tensorler = []

    def run(self, cikti_adlari, girdi):
        tensor = next(iter(girdi.values()))
        self.tensorler.append(tensor)
        # Karo merkezinde 40x40 kutu, skor 0.9.
        orta = tensor.shape[2] / 2
        return [np.array([[[orta], [orta], [40.0], [40.0], [0.9]]], dtype=np.float32)]


def dedektor(giris_boyu=KARO):
    """Oturumu sahte, geri kalani gercek bir OnnxDedektor."""
    d = OnnxDedektor.__new__(OnnxDedektor)
    d.oturum = SayanOturum()
    d.girdi_adi = "images"
    d.girdi_sekli = [1, 3, giris_boyu, giris_boyu]
    d.cikti_adlari = ["output0"]
    d.conf_esigi = settings.DETECTION_STORE_FLOOR
    d.sinif_adlari = {0: "human"}
    d.giris_boyu = giris_boyu
    d.kurulum_suresi = 0.0
    d.kare_sayisi = 0
    d.sayaclar = {"goruntu_okuma": 0.0, "cikarim": 0.0, "son_islem": 0.0}
    d.olcum_sifirla()
    return d


@pytest.fixture
def goruntu(tmp_path):
    """Her bolgesi farkli renkte, gercek bir JPEG."""
    genislik, yukseklik = GORUNTU_OLCU
    dizi = np.zeros((yukseklik, genislik, 3), dtype=np.uint8)
    dizi[:, :genislik // 2] = (200, 30, 30)
    dizi[:, genislik // 2:] = (30, 30, 200)
    dizi[: yukseklik // 2, :] //= 2
    yol = tmp_path / "kare.jpg"
    Image.fromarray(dizi).save(yol, quality=95)
    return yol


@pytest.fixture
def acma_sayaci(monkeypatch):
    """PIL.Image.open cagrilarini sayar ve kapanip kapanmadigini izler."""
    gercek = Image.open
    kayit = {"acma": 0, "acilanlar": []}

    def sayan(fp, *args, **kwargs):
        kayit["acma"] += 1
        nesne = gercek(fp, *args, **kwargs)
        kayit["acilanlar"].append(nesne)
        return nesne

    monkeypatch.setattr("PIL.Image.open", sayan)
    return kayit


def karolar():
    genislik, yukseklik = GORUNTU_OLCU
    return karolari_hesapla(genislik, yukseklik, KARO, ORTUSME)


# --- Kare basina tek okuma ----------------------------------------------------


def test_tek_karo_cagrisinda_goruntu_bir_kez_aciliyor(goruntu, acma_sayaci):
    """Ilk karo goruntuyu bir kez acmali."""
    d = dedektor()
    d.detect(str(goruntu), karolar()[0])
    assert acma_sayaci["acma"] == 1


def test_butun_karolar_icin_goruntu_yalnizca_bir_kez_aciliyor(goruntu, acma_sayaci):
    """Karo sayisi kacsa olsun kare basina tek disk okumasi yapilmali."""
    d = dedektor()
    tum = karolar()
    assert len(tum) > 1, "test anlamli olsun diye birden fazla karo gerekli"
    for karo in tum:
        d.detect(str(goruntu), karo)
    assert acma_sayaci["acma"] == 1


def test_yeni_kare_yeniden_okunuyor(goruntu, tmp_path, acma_sayaci):
    """Farkli bir kaynak goruntu geldiginde yeniden okunmali."""
    ikinci = tmp_path / "ikinci.jpg"
    Image.open(goruntu).save(ikinci)
    acma_sayaci["acma"] = 0

    d = dedektor()
    d.detect(str(goruntu), karolar()[0])
    d.detect(str(ikinci), karolar()[0])
    assert acma_sayaci["acma"] == 2


def test_goruntu_kaynagi_acik_kalmiyor(goruntu, acma_sayaci):
    """Okunan dosya nesnesi acik birakilmamali (hata durumunda da)."""
    d = dedektor()
    d.detect(str(goruntu), karolar()[0])
    assert acma_sayaci["acilanlar"]
    assert all(getattr(g, "fp", None) is None for g in acma_sayaci["acilanlar"])

    # Cikarim patlasa bile kaynak sizmamali.
    class PatlayanOturum:
        def run(self, *a, **k):
            raise RuntimeError("cikarim hatasi")

    d2 = dedektor()
    d2.oturum = PatlayanOturum()
    with pytest.raises(RuntimeError):
        d2.detect(str(goruntu), karolar()[0])
    assert all(getattr(g, "fp", None) is None for g in acma_sayaci["acilanlar"])


# --- Davranis degismiyor ------------------------------------------------------


def karo_diziyi_diskten_oku(yol, karo):
    """Eski akisin yaptigi is: karoyu dogrudan diskten kesip okumak."""
    _, _, x1, y1, x2, y2 = karo
    with Image.open(yol) as gorsel:
        return np.asarray(gorsel.convert("RGB").crop((x1, y1, x2, y2)))


def test_karolar_ayni_bolgeyi_aliyor(goruntu):
    """Bellekten kesilen karo, diskten kesilenle birebir ayni pikselleri vermeli."""
    d = dedektor()
    for karo in karolar():
        beklenen = karo_diziyi_diskten_oku(goruntu, karo)
        alinan = d._karo_dizisi(str(goruntu), karo)
        assert alinan.shape == beklenen.shape
        assert np.array_equal(alinan, beklenen)


def test_tensor_sekli_ve_veri_turu_degismiyor(goruntu):
    """Modele verilen tensor (1, 3, giris, giris) float32 kalmali."""
    d = dedektor()
    d.detect(str(goruntu), karolar()[0])
    tensor = d.oturum.tensorler[0]
    assert tensor.shape == (1, 3, KARO, KARO)
    assert tensor.dtype == np.float32
    assert 0.0 <= float(tensor.min()) and float(tensor.max()) <= 1.0


def test_ayni_sahte_cikti_ayni_kutulari_uretiyor(goruntu):
    """Yeni akis, eski akisla ayni karo kutularini vermeli."""
    yeni = dedektor()
    eski = dedektor()
    for karo in karolar():
        yeni_kutular = yeni.detect(str(goruntu), karo)
        eski_kutular = eski.karo_tahmin_et(karo_diziyi_diskten_oku(goruntu, karo))
        assert len(yeni_kutular) == len(eski_kutular)
        for a, b in zip(yeni_kutular, eski_kutular):
            assert a == pytest.approx(b, abs=1e-6)


def test_karo_koordinatlari_ve_global_donusum_degismiyor(goruntu):
    """Karo duzlemindeki kutu, karo kosesi eklenince goruntu icinde kalmali."""
    genislik, yukseklik = GORUNTU_OLCU
    d = dedektor()
    for satir, sutun, kx1, ky1, kx2, ky2 in karolar():
        for kutu in d.detect(str(goruntu), (satir, sutun, kx1, ky1, kx2, ky2)):
            gx1, gy1, gx2, gy2 = karodan_global_koordinata(kutu[:4], kx1, ky1)
            assert 0 <= gx1 < gx2 <= genislik
            assert 0 <= gy1 < gy2 <= yukseklik


# --- Zamanlama alanlari -------------------------------------------------------


def test_goruntu_okuma_kare_basina_toplam_yukleme_maliyeti(goruntu):
    """Alan anlamini koruyor: kare boyunca gecen toplam yukleme suresi."""
    d = dedektor()
    for karo in karolar():
        d.detect(str(goruntu), karo)
    olcum = d.olcum_al()
    assert olcum["goruntu_okuma"] > 0
    assert olcum["cikarim"] > 0
    assert olcum["son_islem"] >= 0


def test_olcum_sifirlama_yeni_kareyi_sayiyor(goruntu):
    """olcum_sifirla kare sayacini artirir ve sayaclari sifirlar."""
    d = dedektor()
    d.detect(str(goruntu), karolar()[0])
    once = d.olcum_al()["goruntu_okuma"]
    assert once > 0

    d.olcum_sifirla()
    assert d.kare_sayisi == 2
    assert d.olcum_al()["goruntu_okuma"] == 0.0


def test_oturum_kareler_arasinda_ayni_kaliyor(goruntu):
    """Tek okuma degisikligi oturum paylasimini bozmamali."""
    d = dedektor()
    oturum = d.oturum
    d.detect(str(goruntu), karolar()[0])
    d.olcum_sifirla()
    d.detect(str(goruntu), karolar()[1])
    assert d.oturum is oturum
