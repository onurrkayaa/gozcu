"""rapor/ altindaki bolum_*.md dosyalarini numara sirasina gore birlestirir, basina
rapor/kapak.md icerigini ekler ve hem rapor/rapor.md hem rapor/rapor.pdf uretir.
Olcum yapmaz; yalnizca mevcut metinleri birlestirip bicimlendirir."""

from __future__ import annotations

import argparse
import html
import re
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ortak import PROJE_KOK

RAPOR_KOK = PROJE_KOK / "rapor"

# macOS ile birlikte gelen TrueType fontlar. PDF'e gomulduklerinde Turkce
# karakterler (ı, ş, ğ, İ, Ç, Ö, Ü) dogru gorunur; reportlab'in yerlesik
# Helvetica'si bunlari tasimaz.
FONT_ADAYLARI = {
    "Govde": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    "Govde-Bold": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
    "Govde-Italic": [
        "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        "/Library/Fonts/Arial Italic.ttf",
    ],
    "Govde-BoldItalic": [
        "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
        "/Library/Fonts/Arial Bold Italic.ttf",
    ],
    "Kod": [
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ],
}

METIN_RENK = colors.HexColor("#111111")
SOLUK_RENK = colors.HexColor("#555555")
CIZGI_RENK = colors.HexColor("#cccccc")
BASLIK_ZEMIN = colors.HexColor("#f0f0f0")


def argumanlari_coz() -> argparse.Namespace:
    """Komut satiri argumanlarini tanimlar ve cozer."""
    ayrastirici = argparse.ArgumentParser(
        description=(
            "rapor/ altindaki bolum_*.md dosyalarini numara sirasina gore birlestirir, "
            "kapak.md icerigini basa ekler ve rapor/rapor.md ile rapor/rapor.pdf "
            "dosyalarini uretir. Yeni olcum yapmaz."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--rapor-kok", type=Path, default=RAPOR_KOK, help="Bolum dosyalarinin bulundugu klasor")
    ayrastirici.add_argument("--kapak", type=Path, default=None, help="Kapak dosyasi (varsayilan: <rapor-kok>/kapak.md)")
    ayrastirici.add_argument("--md-cikti", type=Path, default=None, help="Birlesik markdown yolu (varsayilan: <rapor-kok>/rapor.md)")
    ayrastirici.add_argument("--pdf-cikti", type=Path, default=None, help="PDF yolu (varsayilan: <rapor-kok>/rapor.pdf)")
    ayrastirici.add_argument("--pdf-yok", action="store_true", help="Sadece birlesik markdown uret, PDF uretme")
    return ayrastirici.parse_args()


def fontlari_kaydet() -> bool:
    """Sistemdeki TrueType fontlari reportlab'e tanitir. Hicbiri bulunamazsa False
    doner ve cagiran taraf yerlesik fontlara duser."""
    kayitli = {}
    for ad, adaylar in FONT_ADAYLARI.items():
        for yol in adaylar:
            if Path(yol).is_file():
                try:
                    pdfmetrics.registerFont(TTFont(ad, yol))
                    kayitli[ad] = yol
                    break
                except Exception:
                    continue
    if "Govde" not in kayitli:
        return False
    # Eksik varyantlar duz govdeye duser; boylece kalin/italik istekleri hata vermez.
    for varyant in ("Govde-Bold", "Govde-Italic", "Govde-BoldItalic"):
        if varyant not in kayitli:
            pdfmetrics.registerFont(TTFont(varyant, kayitli["Govde"]))
    # Aileye font ADLARI yazilir, dosya YOLU degil: reportlab kalin-italik bir
    # parcayla karsilastiginda bu degeri yuz adi olarak arar ve yol yazilirsa
    # KeyError ile tum uretimi durdurur.
    pdfmetrics.registerFontFamily(
        "Govde", normal="Govde", bold="Govde-Bold", italic="Govde-Italic",
        boldItalic="Govde-BoldItalic",
    )
    return True


def bolumleri_bul(rapor_kok: Path) -> list[Path]:
    """bolum_NN.md dosyalarini numara sirasina gore dondurur."""
    dosyalar = sorted(
        rapor_kok.glob("bolum_*.md"),
        key=lambda p: int(re.search(r"bolum_(\d+)", p.stem).group(1)),
    )
    if not dosyalar:
        raise SystemExit(f"'{rapor_kok}' altinda bolum_*.md dosyasi bulunamadi.")
    return dosyalar


def kapagi_oku(kapak: Path) -> str:
    """Kapak metnini okur ve icindeki {tarih} yer tutucusunu bugunun tarihiyle doldurur."""
    if not kapak.is_file():
        raise SystemExit(f"Kapak dosyasi bulunamadi: {kapak}")
    return kapak.read_text(encoding="utf-8").replace("{tarih}", date.today().strftime("%d.%m.%Y"))


def birlestir(kapak_metni: str, bolumler: list[Path]) -> str:
    """Kapak ve bolum metinlerini tek bir markdown belgesinde birlestirir."""
    parcalar = [kapak_metni.rstrip()]
    for yol in bolumler:
        parcalar.append(yol.read_text(encoding="utf-8").strip())
    return "\n\n".join(parcalar) + "\n"


def gorsel_yollarini_tasi(markdown: str, hedef_dizin: Path,
                          kaynak_dizin: Path | None = None) -> str:
    """Gorsel yollarini birlesik belgenin KENDI klasorune gore yeniden yazar.

    Markdown'i oldugu gibi goruntuleyen yerler (GitHub dahil) goreli yollari
    DOSYANIN bulundugu klasore gore cozer. Bolum dosyalari `rapor/` altinda
    durur ve yollari da oraya goredir; birlesik belge baska bir klasore
    yazilirsa bu yollar kirilir. Dosya diskte bulunabiliyorsa yol hedefe gore
    yeniden yazilir, bulunamiyorsa oldugu gibi birakilir.

    Yol once kaynak klasore, sonra depo kokune gore aranir."""
    import os

    kokler = [k for k in (kaynak_dizin, PROJE_KOK) if k is not None]

    def degistir(eslesme: re.Match) -> str:
        aciklama, yol_metni = eslesme.group(1), eslesme.group(2)
        for kok in kokler:
            kaynak = (kok / yol_metni).resolve()
            if kaynak.is_file():
                goreceli = os.path.relpath(kaynak, hedef_dizin.resolve())
                return f"![{aciklama}]({goreceli})"
        return eslesme.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", degistir, markdown)


# --- Markdown -> PDF -----------------------------------------------------------


def satir_ici(metin: str) -> str:
    """Satir ici markdown isaretlemesini reportlab'in anladigi etiketlere cevirir.
    Once XML kacisi yapilir, boylece metindeki < > & karakterleri bozulmaz."""
    metin = html.escape(metin, quote=False)
    # Kod parcalari once islenir; icindeki yildizlar bicimlendirme sayilmasin.
    metin = re.sub(r"`([^`]+)`", r'<font face="Kod" size="8.5">\1</font>', metin)
    metin = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", metin)
    metin = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", metin)
    # [metin](baglanti) -> sadece metin; PDF'te ciplak URL gurultu yapiyor.
    metin = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", metin)
    return metin


def stiller() -> dict[str, ParagraphStyle]:
    """Belgede kullanilan paragraf stillerini uretir."""
    temel = getSampleStyleSheet()
    ortak = {"fontName": "Govde", "textColor": METIN_RENK}
    return {
        "kapak_baslik": ParagraphStyle("kapak_baslik", parent=temel["Title"],
                                       fontName="Govde-Bold", fontSize=24, leading=30,
                                       spaceAfter=14, alignment=TA_CENTER, textColor=METIN_RENK),
        "kapak_alt": ParagraphStyle("kapak_alt", parent=temel["Normal"], fontName="Govde",
                                    fontSize=12, leading=17, alignment=TA_CENTER,
                                    spaceAfter=8, textColor=SOLUK_RENK),
        "h2": ParagraphStyle("h2", parent=temel["Heading1"], fontName="Govde-Bold",
                             fontSize=17, leading=22, spaceBefore=18, spaceAfter=10,
                             textColor=METIN_RENK),
        "h3": ParagraphStyle("h3", parent=temel["Heading2"], fontName="Govde-Bold",
                             fontSize=13, leading=17, spaceBefore=14, spaceAfter=7,
                             textColor=METIN_RENK),
        "h4": ParagraphStyle("h4", parent=temel["Heading3"], fontName="Govde-Bold",
                             fontSize=11, leading=15, spaceBefore=11, spaceAfter=5,
                             textColor=METIN_RENK),
        "govde": ParagraphStyle("govde", parent=temel["Normal"], fontSize=9.6, leading=14.2,
                                spaceAfter=7, alignment=TA_JUSTIFY, **ortak),
        "liste": ParagraphStyle("liste", parent=temel["Normal"], fontSize=9.6, leading=14.2,
                                leftIndent=12, bulletIndent=3, spaceAfter=3, **ortak),
        "alinti": ParagraphStyle("alinti", parent=temel["Normal"], fontSize=9.3, leading=13.6,
                                 leftIndent=14, rightIndent=8, spaceAfter=6,
                                 fontName="Govde-Italic", textColor=SOLUK_RENK),
        "kod": ParagraphStyle("kod", parent=temel["Normal"], fontName="Kod", fontSize=8,
                              leading=10.5, leftIndent=8, textColor=METIN_RENK),
        "tablo_hucre": ParagraphStyle("tablo_hucre", parent=temel["Normal"], fontName="Govde",
                                      fontSize=8.2, leading=11, textColor=METIN_RENK),
        "tablo_baslik": ParagraphStyle("tablo_baslik", parent=temel["Normal"],
                                       fontName="Govde-Bold", fontSize=8.2, leading=11,
                                       textColor=METIN_RENK),
        "gorsel_aciklama": ParagraphStyle("gorsel_aciklama", parent=temel["Normal"],
                                          fontName="Govde-Italic", fontSize=8.4,
                                          leading=11.5, alignment=TA_CENTER,
                                          spaceBefore=4, spaceAfter=10,
                                          textColor=SOLUK_RENK),
    }


def tablo_uret(satirlar: list[str], st: dict, genislik: float) -> Table:
    """Markdown tablo satirlarini reportlab Table nesnesine cevirir. Hucreler
    Paragraph olarak sarildigi icin uzun metinler satir sonuna gelince kirilir."""
    ayristirilmis = []
    for satir in satirlar:
        hucreler = [h.strip() for h in satir.strip().strip("|").split("|")]
        ayristirilmis.append(hucreler)

    # Ikinci satir hizalama satiridir (---|---), tabloya alinmaz.
    baslik = ayristirilmis[0]
    govde = ayristirilmis[2:] if len(ayristirilmis) > 2 else []

    veri = [[Paragraph(satir_ici(h), st["tablo_baslik"]) for h in baslik]]
    for satir in govde:
        # Eksik hucreleri bos ile tamamla; bozuk tablo yuzunden cizim patlamasin.
        satir = satir + [""] * (len(baslik) - len(satir))
        veri.append([Paragraph(satir_ici(h), st["tablo_hucre"]) for h in satir[:len(baslik)]])

    tablo = Table(veri, colWidths=[genislik / len(baslik)] * len(baslik), repeatRows=1)
    tablo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BASLIK_ZEMIN),
        ("GRID", (0, 0), (-1, -1), 0.4, CIZGI_RENK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tablo


#: Gorselin altindaki aciklama yazisi ve bosluklar icin ayrilan yer (punto).
#: Gorsel, cerceve yuksekliginden bu kadari dusuldukten sonrasina sigdirilir.
GORSEL_ACIKLAMA_PAYI = 34


def gorsel_uret(yol_metni: str, aciklama: str, st: dict, genislik: float,
                yukseklik: float, kokler: list[Path]) -> list:
    """Markdown resim sozdiziminden bir gorsel ve altina aciklama yazisi uretir.

    Gorsel, en-boy orani korunarak sayfaya sigdirilir. Olcek HEM genislige HEM
    yukseklige bakar: rapordaki ekran goruntulerinin bir kismi dar ve cok uzun
    (bir tarayici sayfasinin tamami). Yalnizca genislige bakilirsa bunlar
    cerceveden tasar ve reportlab tum PDF uretimini LayoutError ile durdurur.
    """
    aday = None
    for kok in kokler:
        olasi = (kok / yol_metni).resolve()
        if olasi.is_file():
            aday = olasi
            break
    if aday is None:
        # Gorsel bulunamazsa rapor uretimi durmasin; yerine not birakilir.
        return [Paragraph(f"[gorsel bulunamadi: {html.escape(yol_metni)}]", st["gorsel_aciklama"])]

    from reportlab.lib.utils import ImageReader

    asil_g, asil_y = ImageReader(str(aday)).getSize()
    kullanilabilir_y = max(yukseklik - GORSEL_ACIKLAMA_PAYI, 1)
    olcek = min(genislik / asil_g, kullanilabilir_y / asil_y, 1.0)
    parcalar = [Spacer(1, 6),
                Image(str(aday), width=asil_g * olcek, height=asil_y * olcek)]
    if aciklama:
        parcalar.append(Paragraph(satir_ici(aciklama), st["gorsel_aciklama"]))
    else:
        parcalar.append(Spacer(1, 8))
    return parcalar


def akis_uret(markdown: str, st: dict, genislik: float, yukseklik: float,
              kokler: list[Path] | None = None) -> list:
    """Markdown metnini reportlab akis nesnelerine (Flowable) cevirir."""
    akis: list = []
    kokler = kokler or [PROJE_KOK]
    satirlar = markdown.split("\n")
    i = 0
    kapak_bitti = False

    while i < len(satirlar):
        satir = satirlar[i]
        kirpik = satir.strip()

        if not kirpik:
            i += 1
            continue

        # Kod blogu
        if kirpik.startswith("```"):
            i += 1
            kod_satirlari = []
            while i < len(satirlar) and not satirlar[i].strip().startswith("```"):
                kod_satirlari.append(html.escape(satirlar[i], quote=False))
                i += 1
            i += 1
            if kod_satirlari:
                akis.append(Spacer(1, 3))
                for k in kod_satirlari:
                    akis.append(Paragraph(k.replace(" ", "&nbsp;") or "&nbsp;", st["kod"]))
                akis.append(Spacer(1, 7))
            continue

        # Gorsel: ![aciklama](yol)
        gorsel = re.fullmatch(r"!\[(.*)\]\(([^)]+)\)", kirpik)
        if gorsel:
            akis.extend(gorsel_uret(gorsel.group(2), gorsel.group(1), st,
                                    genislik, yukseklik, kokler))
            i += 1
            continue

        # Tablo
        if kirpik.startswith("|") and i + 1 < len(satirlar) and set(satirlar[i + 1].strip()) <= set("|-: "):
            tablo_satirlari = []
            while i < len(satirlar) and satirlar[i].strip().startswith("|"):
                tablo_satirlari.append(satirlar[i])
                i += 1
            akis.append(Spacer(1, 4))
            akis.append(tablo_uret(tablo_satirlari, st, genislik))
            akis.append(Spacer(1, 9))
            continue

        # Yatay cizgi
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", kirpik):
            akis.append(Spacer(1, 5))
            akis.append(HRFlowable(width="100%", thickness=0.5, color=CIZGI_RENK))
            akis.append(Spacer(1, 7))
            i += 1
            continue

        # Basliklar
        baslik = re.match(r"^(#{1,4})\s+(.*)", kirpik)
        if baslik:
            seviye, metin = len(baslik.group(1)), baslik.group(2)
            if seviye == 1:
                # Kapak basligi: kendi sayfasinda durur.
                akis.append(Spacer(1, 55 * mm))
                akis.append(Paragraph(satir_ici(metin), st["kapak_baslik"]))
                kapak_bitti = True
            else:
                if kapak_bitti:
                    # Kapaktan sonraki ilk baslikta govde baslar. Ana bolum
                    # basligiysa (##) yeni sayfaya gecilir.
                    if seviye == 2:
                        akis.append(PageBreak())
                    kapak_bitti = False
                anahtar = {2: "h2", 3: "h3", 4: "h4"}[seviye]
                akis.append(KeepTogether([Paragraph(satir_ici(metin), st[anahtar])]))
            i += 1
            continue

        # Alinti
        if kirpik.startswith(">"):
            alinti_satirlari = []
            while i < len(satirlar) and satirlar[i].strip().startswith(">"):
                alinti_satirlari.append(satirlar[i].strip().lstrip(">").strip())
                i += 1
            akis.append(Paragraph(satir_ici(" ".join(alinti_satirlari)), st["alinti"]))
            continue

        # Liste ogesi
        liste = re.match(r"^([-*]|\d+\.)\s+(.*)", kirpik)
        if liste:
            isaret = "•" if liste.group(1) in ("-", "*") else liste.group(1)
            parcalar = [liste.group(2)]
            i += 1
            # Devam satirlarini (girintili) ayni ogeye ekle.
            while i < len(satirlar) and satirlar[i].startswith(("  ", "\t")) and satirlar[i].strip():
                parcalar.append(satirlar[i].strip())
                i += 1
            akis.append(Paragraph(satir_ici(" ".join(parcalar)), st["liste"], bulletText=isaret))
            continue

        # Duz paragraf: bos satira kadar birlestir.
        parcalar = [kirpik]
        i += 1
        while i < len(satirlar) and satirlar[i].strip() and not re.match(
            r"^(#{1,4}\s|\||>|```|!\[|[-*]\s|\d+\.\s|-{3,}$)", satirlar[i].strip()
        ):
            parcalar.append(satirlar[i].strip())
            i += 1
        birlesik = " ".join(parcalar)
        stil = st["kapak_alt"] if kapak_bitti else st["govde"]
        akis.append(Paragraph(satir_ici(birlesik), stil))

    return akis


def pdf_uret(markdown: str, hedef: Path, kokler: list[Path]) -> Path:
    """Birlesik markdown metninden PDF uretir."""
    hedef.parent.mkdir(parents=True, exist_ok=True)
    belge = SimpleDocTemplate(
        str(hedef), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=hedef.stem, author="",
    )
    st = stiller()
    genislik = belge.width

    def sayfa_alti(tuval, _belge):
        """Her sayfanin altina sayfa numarasi basar."""
        tuval.saveState()
        tuval.setFont("Govde", 8)
        tuval.setFillColor(SOLUK_RENK)
        tuval.drawCentredString(A4[0] / 2, 10 * mm, str(tuval.getPageNumber()))
        tuval.restoreState()

    belge.build(akis_uret(markdown, st, genislik, belge.height, kokler),
                onFirstPage=sayfa_alti, onLaterPages=sayfa_alti)
    return hedef


def main() -> None:
    """Bolumleri birlestirir, markdown ve PDF ciktilarini uretir."""
    arg = argumanlari_coz()
    kapak = arg.kapak or arg.rapor_kok / "kapak.md"
    md_cikti = arg.md_cikti or arg.rapor_kok / "rapor.md"
    pdf_cikti = arg.pdf_cikti or arg.rapor_kok / "rapor.pdf"

    bolumler = bolumleri_bul(arg.rapor_kok)
    print(f"Bulunan bolumler ({len(bolumler)}):")
    for yol in bolumler:
        satir_sayisi = len(yol.read_text(encoding="utf-8").splitlines())
        print(f"  {yol.name}  ({satir_sayisi} satir)")

    birlesik = birlestir(kapagi_oku(kapak), bolumler)
    md_cikti.parent.mkdir(parents=True, exist_ok=True)
    birlesik = gorsel_yollarini_tasi(birlesik, md_cikti.parent, arg.rapor_kok)
    md_cikti.write_text(birlesik, encoding="utf-8")
    print(f"\nMarkdown : {md_cikti}  ({len(birlesik.split())} kelime)")

    if arg.pdf_yok:
        return

    if not fontlari_kaydet():
        raise SystemExit(
            "Sistemde gomulebilir TrueType font bulunamadi. PDF uretmeden cikiliyor;\n"
            "birlesik markdown yazildi. --pdf-yok ile bu adimi atlayabilirsiniz."
        )
    # Gorsel yollari once rapor klasorune, sonra proje kokune gore aranir.
    print(f"PDF      : {pdf_uret(birlesik, pdf_cikti, [md_cikti.parent, arg.rapor_kok, PROJE_KOK])}")


if __name__ == "__main__":
    main()
