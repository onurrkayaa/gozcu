"""11_karo_veri_hazirla.py icindeki saf karolama mantiginin testleri.

Testler goruntu acmaz, dosya yazmaz: sadece kutu-karo geometrisi, gorunurluk
kurali, karo kategorisi ve negatif ornekleme belirlenimciligi olculur.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

PROJE_KOK = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIZIN = PROJE_KOK / "scripts"

# Dosya adi rakamla basladigi icin normal import edilemez; yoldan yukluyoruz.
# scripts/ ve backend/ yola ekleniyor ki modulun kendi importlari (ortak,
# core.tiling) cozulebilsin.
sys.path.insert(0, str(SCRIPT_DIZIN))
sys.path.insert(0, str(PROJE_KOK / "backend"))

_spec = importlib.util.spec_from_file_location(
    "karo_veri", SCRIPT_DIZIN / "11_karo_veri_hazirla.py"
)
karo_veri = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(karo_veri)

MEDYAN_KUTU_PX = 60  # Hafta 0 olcumu: medyan kutu 60x59 px.


# --- Kutu -> karo koordinat cevrimi -------------------------------------------


def test_koordinat_cevrimi_elle_hesaplanan_deger():
    """Bilinen bir kutu ve bilinen bir karo icin elle hesaplanan YOLO degerleri.

    Karo (240,480)-(560,800), 320 px. Kutu (300,500)-(360,560) tamamen iceride.
    Karo duzleminde (60,20)-(120,80) olur; 320'ye bolunur.
    """
    sonuc = karo_veri.kutuyu_karoya_tasi(
        (300, 500, 360, 560), (240, 480, 560, 800), min_gorunur=0.6
    )
    xm, ym, g, y = sonuc
    assert xm == pytest.approx(90 / 320)
    assert ym == pytest.approx(50 / 320)
    assert g == pytest.approx(60 / 320)
    assert y == pytest.approx(60 / 320)


def test_kutu_tamamen_karo_icindeyse_boyutu_korunuyor():
    """Tam iceride kalan bir kutu kirpilmamali; genislik ve yukseklik aynen kalmali."""
    karo = (0, 0, 320, 320)
    _, _, g, y = karo_veri.kutuyu_karoya_tasi((100, 150, 160, 210), karo, 0.6)
    assert g * 320 == pytest.approx(60)
    assert y * 320 == pytest.approx(60)
    assert karo_veri.gorunur_oran((100, 150, 160, 210), karo) == pytest.approx(1.0)


def test_kutu_karonun_tamamen_disindaysa_dahil_edilmiyor():
    """Karoyla hic kesismeyen kutu o karoya girmez."""
    karo = (0, 0, 320, 320)
    assert karo_veri.gorunur_oran((1000, 1000, 1060, 1060), karo) == 0.0
    assert karo_veri.kutuyu_karoya_tasi((1000, 1000, 1060, 1060), karo, 0.6) is None


def test_kismen_iceride_ve_gorunur_oran_esigin_ustunde_kirpilmis_dahil():
    """60x60 kutunun 40 px'i iceride: oran 0,667 > 0,6 -> kirpilmis haliyle girer."""
    karo = (0, 0, 320, 320)
    kutu = (280, 100, 340, 160)
    assert karo_veri.gorunur_oran(kutu, karo) == pytest.approx(40 / 60)

    xm, ym, g, y = karo_veri.kutuyu_karoya_tasi(kutu, karo, 0.6)
    assert xm == pytest.approx(300 / 320)
    assert ym == pytest.approx(130 / 320)
    assert g == pytest.approx(40 / 320)  # 60 degil: kirpildi
    assert y == pytest.approx(60 / 320)


def test_kismen_iceride_ve_gorunur_oran_esigin_altinda_atlaniyor():
    """60x60 kutunun 20 px'i iceride: oran 0,333 < 0,6 -> bu karoda atlanir."""
    karo = (0, 0, 320, 320)
    kutu = (300, 100, 360, 160)
    assert karo_veri.gorunur_oran(kutu, karo) == pytest.approx(20 / 60)
    assert karo_veri.kutuyu_karoya_tasi(kutu, karo, 0.6) is None


def test_gorunur_oran_esigin_tam_uzerindeki_kutu_dahil():
    """Esik dahil olmali: oran tam 0,6 ise kutu atlanmaz."""
    karo = (0, 0, 320, 320)
    kutu = (284, 100, 344, 160)  # 36/60 = 0,6
    assert karo_veri.gorunur_oran(kutu, karo) == pytest.approx(0.6)
    assert karo_veri.kutuyu_karoya_tasi(kutu, karo, 0.6) is not None


def test_uretilen_etiketler_0_1_araliginda_normalize():
    """YOLO formati kurali: tum degerler [0,1] icinde ve kutu karo disina tasmiyor."""
    karo = (240, 480, 560, 800)
    kutular = [
        (300, 500, 360, 560),   # tam iceride
        (520, 500, 580, 560),   # sag kenarda kirpilir
        (250, 460, 310, 520),   # ust kenarda kirpilir
        (240, 480, 300, 540),   # sol ust koseye yapisik
    ]
    for kutu in kutular:
        sonuc = karo_veri.kutuyu_karoya_tasi(kutu, karo, 0.6)
        if sonuc is None:
            continue
        xm, ym, g, y = sonuc
        assert 0.0 <= xm <= 1.0 and 0.0 <= ym <= 1.0
        assert 0.0 < g <= 1.0 and 0.0 < y <= 1.0
        # Merkez +- yari kenar da karo disina tasmamali.
        assert xm - g / 2 >= -1e-9 and xm + g / 2 <= 1.0 + 1e-9
        assert ym - y / 2 >= -1e-9 and ym + y / 2 <= 1.0 + 1e-9


# --- Karo kategorisi ----------------------------------------------------------


def test_kategori_belirsiz_karo_negatif_sayilmiyor():
    """Icinde insan olan ama gorunurluk kuralini gecemeyen karo BELIRSIZ'dir.

    Bu karo negatif havuzuna girerse modele 'yarim insan = arka plan' ogretilir;
    bu yuzden ne pozitif ne negatif sayilir, hicbir yere yazilmaz.
    """
    karo = (0, 0, 320, 320)
    assert karo_veri.karo_kategorisi([(300, 100, 360, 160)], karo, 0.6) == "belirsiz"
    assert karo_veri.karo_kategorisi([(100, 100, 160, 160)], karo, 0.6) == "pozitif"
    assert karo_veri.karo_kategorisi([(1000, 1000, 1060, 1060)], karo, 0.6) == "negatif"
    assert karo_veri.karo_kategorisi([], karo, 0.6) == "negatif"


def test_kategori_bir_kutu_gecerse_karo_pozitif():
    """Biri gecip biri elenirse karo pozitiftir; elenen etiket sadece o karoda atlanir."""
    karo = (0, 0, 320, 320)
    kutular = [(100, 100, 160, 160), (300, 100, 360, 160)]
    assert karo_veri.karo_kategorisi(kutular, karo, 0.6) == "pozitif"


# --- Negatif ornekleme --------------------------------------------------------


def test_negatif_ornekleme_ayni_tohumla_ayni_sonuc():
    """Ayni tohum ayni ornegi vermeli; tekrarlanabilirligin sarti budur."""
    adaylar = [("g%d" % i, i // 10, i % 10) for i in range(200)]
    a = karo_veri.negatif_ornekle(adaylar, 30, tohum=0)
    b = karo_veri.negatif_ornekle(adaylar, 30, tohum=0)
    assert a == b
    assert len(a) == 30
    assert set(a).issubset(set(adaylar))
    assert len(set(a)) == 30  # ayni aday iki kez secilmez


def test_negatif_ornekleme_istenen_sayi_aday_sayisini_asarsa_hepsi_doner():
    """Yeterli negatif aday yoksa var olanlarin hepsi alinir, hata verilmez."""
    adaylar = [("g", 0, i) for i in range(5)]
    assert sorted(karo_veri.negatif_ornekle(adaylar, 50, tohum=0)) == sorted(adaylar)


# --- Ortusme piksel hesabi ----------------------------------------------------


def test_ortusme_piksel_hesabi_medyan_kutudan_buyuk():
    """Varsayilan karo/ortusme ciftlerinde ortusme, medyan kutudan (60 px) buyuk olmali.

    Ortusme medyan kutudan kucuk olsaydi iki karonun arasina dusen bir hedef
    hicbir karoda butun kalmaz ve %60 kurali onu ikisinden de atardi.
    256 x 0,30 = 76,8; tiling.py int() ile kirptigi icin sonuc 76 px'tir.
    """
    assert karo_veri.ortusme_piksel(256, 0.30) == 76
    assert karo_veri.ortusme_piksel(320, 0.25) == 80
    assert karo_veri.ortusme_piksel(512, 0.20) == 102

    for karo, oran in karo_veri.VARSAYILAN_ORTUSME.items():
        assert karo_veri.ortusme_piksel(karo, oran) > MEDYAN_KUTU_PX
