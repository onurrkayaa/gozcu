"""ortak.py icindeki IoU hesabi ve tahmin-gercek eslestirme mantiginin testleri."""

import sys
from pathlib import Path

import pytest

# scripts/ klasoru bir paket degil; testin ortak.py'yi bulabilmesi icin yola ekliyoruz.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ortak import Kutu, iou_hesapla, kutulari_eslestir, metrik_hesapla  # noqa: E402


# --- IoU hesabi ---------------------------------------------------------------


def test_iou_tam_ortusme():
    """Ayni konumdaki iki kutunun IoU degeri 1.0 olmali."""
    a = Kutu(10, 10, 50, 50)
    b = Kutu(10, 10, 50, 50)
    assert iou_hesapla(a, b) == pytest.approx(1.0)


def test_iou_hic_ortusmeme():
    """Birbirine deymeyen iki kutunun IoU degeri 0.0 olmali."""
    a = Kutu(0, 0, 10, 10)
    b = Kutu(100, 100, 110, 110)
    assert iou_hesapla(a, b) == pytest.approx(0.0)


def test_iou_kismi_ortusme():
    """Yarim ust uste binen kutularda IoU = kesisim / birlesim olmali."""
    # a: 0-10 x 0-10 (alan 100), b: 5-15 x 0-10 (alan 100)
    # kesisim: 5-10 x 0-10 = 50, birlesim: 100 + 100 - 50 = 150
    a = Kutu(0, 0, 10, 10)
    b = Kutu(5, 0, 15, 10)
    assert iou_hesapla(a, b) == pytest.approx(50 / 150)


def test_iou_sadece_kenar_deger():
    """Sadece kenardan deyen kutularda kesisim alani sifir oldugu icin IoU 0.0 olmali."""
    a = Kutu(0, 0, 10, 10)
    b = Kutu(10, 0, 20, 10)
    assert iou_hesapla(a, b) == pytest.approx(0.0)


def test_iou_ic_ice_kutu():
    """Kucuk kutu buyugun tamamen icindeyse IoU = kucuk alan / buyuk alan olmali."""
    buyuk = Kutu(0, 0, 20, 20)  # alan 400
    kucuk = Kutu(5, 5, 15, 15)  # alan 100
    assert iou_hesapla(buyuk, kucuk) == pytest.approx(100 / 400)


# --- Eslestirme ---------------------------------------------------------------


def test_eslestirme_tam_ortusme_hepsi_eslesir():
    """Tahminler gercek kutularla birebir ayni ise hepsi eslesmeli, artan olmamali."""
    gercekler = [Kutu(0, 0, 10, 10), Kutu(50, 50, 60, 60)]
    tahminler = [Kutu(0, 0, 10, 10, skor=0.9), Kutu(50, 50, 60, 60, skor=0.8)]

    eslesmeler, eslesmeyen_g, eslesmeyen_t = kutulari_eslestir(gercekler, tahminler, 0.3)

    assert len(eslesmeler) == 2
    assert eslesmeyen_g == []
    assert eslesmeyen_t == []


def test_eslestirme_hic_ortusmeme_hicbiri_eslesmez():
    """Uzaktaki tahminler hicbir gercekle eslesmemeli; hepsi FN ve FP olarak kalmali."""
    gercekler = [Kutu(0, 0, 10, 10)]
    tahminler = [Kutu(500, 500, 510, 510, skor=0.9)]

    eslesmeler, eslesmeyen_g, eslesmeyen_t = kutulari_eslestir(gercekler, tahminler, 0.3)

    assert eslesmeler == []
    assert eslesmeyen_g == [0]
    assert eslesmeyen_t == [0]


def test_eslestirme_kismi_ortusme_esik_belirleyici():
    """IoU esigin altinda kalan kismi ortusme eslesmemeli, esigin ustundeki eslesmeli."""
    gercekler = [Kutu(0, 0, 10, 10)]
    # IoU = 50/150 = 0.333
    tahminler = [Kutu(5, 0, 15, 10, skor=0.9)]

    # Esik 0.3 -> eslesir
    eslesmeler, eslesmeyen_g, _ = kutulari_eslestir(gercekler, tahminler, 0.3)
    assert len(eslesmeler) == 1
    assert eslesmeyen_g == []

    # Esik 0.5 -> eslesmez
    eslesmeler, eslesmeyen_g, eslesmeyen_t = kutulari_eslestir(gercekler, tahminler, 0.5)
    assert eslesmeler == []
    assert eslesmeyen_g == [0]
    assert eslesmeyen_t == [0]


def test_eslestirme_bir_gercek_en_fazla_bir_tahmin():
    """Ayni gercek kutuyu ortan iki tahminden sadece yuksek skorlu olan eslesmeli."""
    gercekler = [Kutu(0, 0, 10, 10)]
    tahminler = [
        Kutu(0, 0, 10, 10, skor=0.4),   # indeks 0, dusuk skor
        Kutu(0, 0, 10, 10, skor=0.95),  # indeks 1, yuksek skor
    ]

    eslesmeler, eslesmeyen_g, eslesmeyen_t = kutulari_eslestir(gercekler, tahminler, 0.3)

    assert len(eslesmeler) == 1
    # Eslesen tahmin, yuksek skorlu olan (indeks 1) olmali.
    assert eslesmeler[0][1] == 1
    assert eslesmeyen_g == []
    assert eslesmeyen_t == [0]


def test_eslestirme_yuksek_skorlu_tahmin_oncelikli_secer():
    """Yuksek skorlu tahmin once islenir ve daha iyi ortustugu gercegi kapar."""
    gercekler = [Kutu(0, 0, 10, 10), Kutu(8, 0, 18, 10)]
    tahminler = [Kutu(8, 0, 18, 10, skor=0.99)]

    eslesmeler, _, _ = kutulari_eslestir(gercekler, tahminler, 0.3)

    assert len(eslesmeler) == 1
    # Tahmin, 1 numarali gercekle birebir ortustugu icin onu secmeli.
    assert eslesmeler[0][0] == 1


def test_eslestirme_bos_girdiler():
    """Gercek ya da tahmin listesi bos oldugunda fonksiyon hata vermemeli."""
    assert kutulari_eslestir([], [], 0.3) == ([], [], [])

    eslesmeler, eslesmeyen_g, eslesmeyen_t = kutulari_eslestir(
        [Kutu(0, 0, 10, 10)], [], 0.3
    )
    assert eslesmeler == [] and eslesmeyen_g == [0] and eslesmeyen_t == []

    eslesmeler, eslesmeyen_g, eslesmeyen_t = kutulari_eslestir(
        [], [Kutu(0, 0, 10, 10, skor=0.5)], 0.3
    )
    assert eslesmeler == [] and eslesmeyen_g == [] and eslesmeyen_t == [0]


def test_eslestirme_tekrarlanabilir():
    """Ayni girdi ile iki kez calistirildiginda sonuc birebir ayni olmali."""
    gercekler = [Kutu(0, 0, 10, 10), Kutu(20, 20, 30, 30), Kutu(40, 40, 50, 50)]
    tahminler = [
        Kutu(0, 0, 10, 10, skor=0.5),
        Kutu(21, 21, 31, 31, skor=0.5),
        Kutu(200, 200, 210, 210, skor=0.5),
    ]

    birinci = kutulari_eslestir(gercekler, tahminler, 0.3)
    ikinci = kutulari_eslestir(gercekler, tahminler, 0.3)
    assert birinci == ikinci


# --- Metrikler ----------------------------------------------------------------


def test_metrik_hesapla_temel():
    """TP/FN/FP sayimlarindan recall, precision ve FP/goruntu dogru uretilmeli."""
    m = metrik_hesapla(tp=8, fn=2, fp=4, goruntu_sayisi=2)

    assert m["gercek_kutu"] == 10
    assert m["recall"] == pytest.approx(0.8)
    assert m["precision"] == pytest.approx(8 / 12)
    assert m["fp_goruntu_basina"] == pytest.approx(2.0)


def test_metrik_hesapla_sifira_bolme_yok():
    """Hic gercek kutu veya hic tahmin olmadiginda metrikler 0.0 donmeli, hata vermemeli."""
    m = metrik_hesapla(tp=0, fn=0, fp=0, goruntu_sayisi=0)
    assert m["recall"] == 0.0
    assert m["precision"] == 0.0
    assert m["fp_goruntu_basina"] == 0.0
