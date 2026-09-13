"""06_rapor_uret.py gorsel olcekleme davranisi.

Rapor gorselleri arasinda uzun ekran goruntuleri var (ornegin bir tarayici
sayfasinin tamami). Bunlar sayfa genisligine sigdirilsa bile YUKSEKLIK olarak
cerceveye sigmiyordu ve reportlab tum PDF uretimini LayoutError ile
durduruyordu. Bu dosya, olceklemenin iki boyutu birden dikkate aldigini
dogrular."""
import importlib.util
import sys
from pathlib import Path

import pytest
from PIL import Image as PILImage

PROJE_KOK = Path(__file__).resolve().parents[2]
SCRIPT_DIZIN = PROJE_KOK / "scripts"

# Dosya adi rakamla basladigi icin normal import edilemez; yoldan yukluyoruz.
sys.path.insert(0, str(SCRIPT_DIZIN))


def _modulu_yukle():
    yol = SCRIPT_DIZIN / "06_rapor_uret.py"
    spec = importlib.util.spec_from_file_location("rapor_uret", yol)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture(scope="module")
def modul():
    m = _modulu_yukle()
    # stiller() "Govde" ailesini bekler; kayitli degilse Paragraph kurulamaz.
    if not m.fontlari_kaydet():
        pytest.skip("Sistemde gomulebilir TrueType font yok; PDF stilleri kurulamiyor.")
    return m


@pytest.fixture
def kok(tmp_path):
    (tmp_path / "gorseller").mkdir()
    return tmp_path


def _gorsel_yaz(kok: Path, ad: str, genislik: int, yukseklik: int) -> str:
    PILImage.new("RGB", (genislik, yukseklik), (200, 200, 200)).save(kok / ad)
    return ad


def test_uzun_gorsel_cerceve_yuksekligine_sigar(modul, kok):
    """Dar ve cok uzun bir gorsel, kullanilabilir yuksekligi asmamali."""
    ad = _gorsel_yaz(kok, "uzun.png", 800, 4000)
    st = modul.stiller()
    parcalar = modul.gorsel_uret(ad, "aciklama", st, genislik=470, yukseklik=720, kokler=[kok])

    gorseller = [p for p in parcalar if hasattr(p, "drawHeight")]
    assert len(gorseller) == 1
    assert gorseller[0].drawHeight <= 720
    assert gorseller[0].drawWidth <= 470


def test_en_boy_orani_korunur(modul, kok):
    ad = _gorsel_yaz(kok, "uzun.png", 800, 4000)
    st = modul.stiller()
    gorsel = [p for p in modul.gorsel_uret(ad, "", st, 470, 720, [kok]) if hasattr(p, "drawHeight")][0]
    assert gorsel.drawHeight / gorsel.drawWidth == pytest.approx(4000 / 800, rel=1e-6)


def test_kucuk_gorsel_buyutulmez(modul, kok):
    """Sayfaya sigan bir gorsel oldugundan buyuk cizilmemeli."""
    ad = _gorsel_yaz(kok, "kucuk.png", 200, 150)
    st = modul.stiller()
    gorsel = [p for p in modul.gorsel_uret(ad, "", st, 470, 720, [kok]) if hasattr(p, "drawHeight")][0]
    assert gorsel.drawWidth == 200
    assert gorsel.drawHeight == 150


def test_bulunamayan_gorsel_uretimi_durdurmaz(modul, kok):
    st = modul.stiller()
    parcalar = modul.gorsel_uret("yok/olmayan.png", "", st, 470, 720, [kok])
    assert len(parcalar) == 1
    assert "bulunamadi" in parcalar[0].text


def test_kalin_italik_font_ailesi_kayitli(modul):
    """<b><i> birlikte kullanildiginda reportlab boldItalic yuzunu arar.

    Aile kaydina font ADI yerine dosya YOLU yazilirsa arama KeyError verir ve
    tum PDF uretimi durur; rapor metninde kalin-italik gecen tek bir satir bile
    bunu tetikler."""
    from reportlab.lib.fonts import tt2ps
    from reportlab.pdfbase import pdfmetrics

    assert modul.fontlari_kaydet()
    for kalin, italik in ((0, 0), (1, 0), (0, 1), (1, 1)):
        yuz = tt2ps("Govde", kalin, italik)
        # Kayitli olmayan bir yuz istenirse burasi KeyError yukseltir.
        assert pdfmetrics.getFont(yuz) is not None


def test_gorsel_yollari_hedef_klasore_gore_yazilir(modul, tmp_path):
    """Birlesik belge rapor/ altinda durur; depo kokune goreli yollar oradan cozulmez."""
    hedef = modul.PROJE_KOK / "rapor"
    metin = "![Ekran](rapor/gorseller/hafta5/01_giris_ekrani.png)"
    sonuc = modul.gorsel_yollarini_tasi(metin, hedef)
    assert sonuc == "![Ekran](gorseller/hafta5/01_giris_ekrani.png)"


def test_bulunamayan_gorsel_yolu_degistirilmez(modul):
    metin = "![Yok](rapor/gorseller/olmayan.png)"
    assert modul.gorsel_yollarini_tasi(metin, modul.PROJE_KOK / "rapor") == metin
