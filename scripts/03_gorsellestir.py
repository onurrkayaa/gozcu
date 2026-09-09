"""Ornek goruntuleri ekrana sigacak boyuta kucultup uzerlerine gercek etiketleri
YESIL, modelin karolamali tahminlerini KIRMIZI kutularla cizer. Tahminlerin guven
skoru kutunun yanina yazilir; sonuclar reports/ornekler/ klasorune kaydedilir."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm

from ortak import (
    RAPOR_KOK,
    VERI_KOK,
    Kutu,
    bolum_yolu,
    etiket_yolu,
    goruntuleri_listele,
    karolamali_tara,
    kutulari_eslestir,
    model_kur,
    yolo_etiket_oku,
)

VARSAYILAN_MODEL = "yolo11n.pt"
GERCEK_RENK = (0, 220, 0)      # yesil: gercek etiket kutulari
TAHMIN_RENK = (255, 40, 40)    # kirmizi: modelin tahminleri
YAZI_RENK = (255, 255, 255)


def argumanlari_coz() -> argparse.Namespace:
    """Komut satiri argumanlarini tanimlar ve cozer."""
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Ornek goruntuleri kucultup gercek kutulari yesil, model tahminlerini "
            "guven skoruyla birlikte kirmizi cizer ve reports/ornekler/ klasorune "
            "kaydeder. Gozle kontrol icindir; metrik hesaplamaz."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Veri kumesi kok klasoru")
    ayrastirici.add_argument("--bolum", default="test", help="Ornek alinacak bolum")
    ayrastirici.add_argument("--adet", type=int, default=10, help="Kac ornek goruntu cizilsin")
    ayrastirici.add_argument("--karo", type=int, default=512, help="Karo kenar uzunlugu, piksel")
    ayrastirici.add_argument("--ortusme", type=float, default=0.2, help="Karolar arasi ortusme orani")
    ayrastirici.add_argument("--conf", type=float, default=0.15, help="Bu esigin altindaki tahminler cizilmez")
    ayrastirici.add_argument("--iou", type=float, default=0.3, help="Ozet satirindaki eslestirme icin IoU esigi")
    ayrastirici.add_argument("--maks-kenar", type=int, default=1600, help="Kaydedilen goruntunun en uzun kenari, piksel")
    ayrastirici.add_argument("--model", default=VARSAYILAN_MODEL, help="Ultralytics model dosyasi")
    ayrastirici.add_argument("--cikti", type=Path, default=RAPOR_KOK / "ornekler", help="Ciktilarin kaydedilecegi klasor")
    return ayrastirici.parse_args()


def yazi_tipi(boyut: int) -> ImageFont.ImageFont:
    """Skor etiketleri icin bir yazi tipi dondurur; sistemde bulunamazsa PIL'in
    varsayilan yazi tipine duser."""
    for aday in ("/System/Library/Fonts/Supplemental/Arial.ttf",
                 "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(aday, boyut)
        except OSError:
            continue
    return ImageFont.load_default()


def kutu_ciz(cizici: ImageDraw.ImageDraw, kutu: Kutu, olcek: float, renk, kalinlik: int) -> None:
    """Bir kutuyu kucultulmus goruntu olcegine tasiyip cerceve olarak cizer."""
    cizici.rectangle(
        [kutu.x1 * olcek, kutu.y1 * olcek, kutu.x2 * olcek, kutu.y2 * olcek],
        outline=renk,
        width=kalinlik,
    )


def skor_yaz(cizici, kutu: Kutu, olcek: float, font, kalinlik: int) -> None:
    """Tahmin kutusunun yanina guven skorunu okunakli bir zemin uzerine yazar."""
    metin = f"{kutu.skor:.2f}"
    x = kutu.x1 * olcek
    y = kutu.y1 * olcek
    sol, ust, sag, alt = cizici.textbbox((0, 0), metin, font=font)
    genislik, yukseklik = sag - sol, alt - ust

    # Etiketi kutunun ustune koy; goruntunun disina tasiyorsa kutunun altina al.
    etiket_y = y - yukseklik - 2 * kalinlik
    if etiket_y < 0:
        etiket_y = kutu.y2 * olcek + kalinlik

    cizici.rectangle(
        [x, etiket_y, x + genislik + 4, etiket_y + yukseklik + 4],
        fill=TAHMIN_RENK,
    )
    cizici.text((x + 2, etiket_y + 2), metin, fill=YAZI_RENK, font=font)


def goruntuyu_isaretle(
    goruntu_yolu: Path,
    gercekler: list[Kutu],
    tahminler: list[Kutu],
    maks_kenar: int,
    hedef: Path,
) -> None:
    """Goruntuyu kucultur, gercek ve tahmin kutularini cizer ve diske kaydeder."""
    with Image.open(goruntu_yolu) as gorsel:
        gorsel = gorsel.convert("RGB")
        genislik, yukseklik = gorsel.size
        # Once kucultup sonra ciziyoruz; tersi yapilirsa ince cerceveler
        # kucultme sirasinda silinip goruntuden kaybolur.
        olcek = min(maks_kenar / genislik, maks_kenar / yukseklik, 1.0)
        kucuk = gorsel.resize(
            (max(1, int(genislik * olcek)), max(1, int(yukseklik * olcek))),
            Image.LANCZOS,
        )

    cizici = ImageDraw.Draw(kucuk)
    kalinlik = max(2, kucuk.width // 500)
    font = yazi_tipi(max(12, kucuk.width // 90))

    for kutu in gercekler:
        kutu_ciz(cizici, kutu, olcek, GERCEK_RENK, kalinlik)
    for kutu in tahminler:
        kutu_ciz(cizici, kutu, olcek, TAHMIN_RENK, kalinlik)
        skor_yaz(cizici, kutu, olcek, font, kalinlik)

    # Sol ust kosede kisa bir aciklama; goruntu tek basina bakildiginda anlasilsin.
    aciklama = f"YESIL = gercek ({len(gercekler)})   KIRMIZI = tahmin ({len(tahminler)})"
    aciklama_font = yazi_tipi(max(14, kucuk.width // 70))
    sol, ust, sag, alt = cizici.textbbox((0, 0), aciklama, font=aciklama_font)
    cizici.rectangle([0, 0, sag - sol + 12, alt - ust + 12], fill=(0, 0, 0))
    cizici.text((6, 6), aciklama, fill=YAZI_RENK, font=aciklama_font)

    hedef.parent.mkdir(parents=True, exist_ok=True)
    kucuk.save(hedef, quality=90)


def main() -> None:
    """Ornek goruntuleri tarar, isaretli kopyalarini kaydeder ve kisa bir ozet basar."""
    arg = argumanlari_coz()

    goruntu_dizin, etiket_dizin = bolum_yolu(arg.bolum, arg.veri)
    goruntuler = goruntuleri_listele(goruntu_dizin, arg.adet)
    if not goruntuler:
        raise SystemExit(f"'{arg.bolum}' bolumunde goruntu bulunamadi.")

    print(f"Bolum: {arg.bolum} | Ornek: {len(goruntuler)} | conf >= {arg.conf} | "
          f"en uzun kenar: {arg.maks_kenar}px")

    model = model_kur(arg.model, arg.conf)
    arg.cikti.mkdir(parents=True, exist_ok=True)

    for sira, yol in enumerate(tqdm(goruntuler, desc="cizim", unit="gor"), start=1):
        with Image.open(yol) as gorsel:
            genislik, yukseklik = gorsel.size
        gercekler = yolo_etiket_oku(etiket_yolu(yol, etiket_dizin), genislik, yukseklik)
        tahminler = [
            k for k in karolamali_tara(model, yol, arg.karo, arg.ortusme)
            if k.skor >= arg.conf
        ]
        eslesmeler, _, _ = kutulari_eslestir(gercekler, tahminler, arg.iou)

        hedef = arg.cikti / f"{sira:02d}_{yol.stem[:40]}.jpg"
        goruntuyu_isaretle(yol, gercekler, tahminler, arg.maks_kenar, hedef)
        tqdm.write(
            f"  {hedef.name}: gercek={len(gercekler)} tahmin={len(tahminler)} "
            f"eslesen={len(eslesmeler)}"
        )

    print(f"\n{len(goruntuler)} ornek kaydedildi: {arg.cikti}")


if __name__ == "__main__":
    main()
