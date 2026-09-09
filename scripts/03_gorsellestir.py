"""Ornek goruntuleri ekrana sigacak boyuta kucultup uzerlerine gercek etiketleri
YESIL, modelin karolamali tahminlerini KIRMIZI kutularla cizer. Ornekler tabakali
secilir: kalabalik sahneler, az etiketli sahneler ve hic etiketi olmayan (negatif)
sahneler birlikte temsil edilsin diye. Sonuclar reports/ornekler/ klasorune yazilir."""

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
    csv_yaz,
    etiket_yolu,
    goruntuleri_listele,
    karolamali_tara,
    kosu_bilgisi,
    kutulari_eslestir,
    model_kur,
    tablo_bas,
    yolo_etiket_oku,
)

VARSAYILAN_MODEL = "yolo11n.pt"
GERCEK_RENK = (0, 220, 0)      # yesil: gercek etiket kutulari
TAHMIN_RENK = (255, 40, 40)    # kirmizi: modelin tahminleri
YAZI_RENK = (255, 255, 255)

# Tabakali orneklem dagilimi. Negatif goruntuler kasten dahil edilir: modelin bos
# arazide urettigi yanlis pozitifler ancak boyle gozle gorulebilir.
KALABALIK_ADET = 4   # en cok etiketi olan sahneler
AZ_ADET = 4          # 1-2 kutulu seyrek sahneler
NEGATIF_ADET = 2     # hic etiketi olmayan sahneler
AZ_ALT_SINIR = 1
AZ_UST_SINIR = 2


def argumanlari_coz() -> argparse.Namespace:
    """Komut satiri argumanlarini tanimlar ve cozer."""
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Tabakali secilmis ornek goruntuleri kucultup gercek kutulari yesil, "
            "model tahminlerini guven skoruyla birlikte kirmizi cizer. Ornekler "
            f"{KALABALIK_ADET} kalabalik + {AZ_ADET} az etiketli + {NEGATIF_ADET} "
            "negatif sahneden olusur. Goruntuler reports/ornekler/ klasorune, secim "
            "listesi reports/ornek_secim.csv olarak kaydedilir. Metrik hesaplamaz; "
            "gozle kontrol icindir."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Veri kumesi kok klasoru")
    ayrastirici.add_argument("--bolum", default="test", help="Ornek alinacak bolum")
    ayrastirici.add_argument(
        "--onek", nargs="+", default=None,
        help=(
            "Sadece bu kaynak oneklerinden ornek secilsin (or. BLI GRO CAB). "
            "Onek, dosya adinin ikinci parcasidir. Verilmezse tum onekler."
        ),
    )
    ayrastirici.add_argument("--karo", type=int, default=512, help="Karo kenar uzunlugu, piksel")
    ayrastirici.add_argument("--ortusme", type=float, default=0.2, help="Karolar arasi ortusme orani")
    ayrastirici.add_argument("--conf", type=float, default=0.15, help="Bu esigin altindaki tahminler cizilmez")
    ayrastirici.add_argument("--iou", type=float, default=0.3, help="Ozet satirindaki eslestirme icin IoU esigi")
    ayrastirici.add_argument("--maks-kenar", type=int, default=1600, help="Kaydedilen goruntunun en uzun kenari, piksel")
    ayrastirici.add_argument("--model", default=VARSAYILAN_MODEL, help="Ultralytics model dosyasi")
    ayrastirici.add_argument("--cikti", type=Path, default=RAPOR_KOK / "ornekler", help="Goruntulerin kaydedilecegi klasor")
    ayrastirici.add_argument(
        "--secim-csv", type=Path, default=RAPOR_KOK / "ornek_secim.csv",
        help="Secilen goruntulerin listesinin yazilacagi CSV",
    )
    return ayrastirici.parse_args()


def onek_cikar(goruntu: Path) -> str:
    """Dosya adindan kaynak onegini cikarir: train_BLI_0012_... -> BLI"""
    parcalar = goruntu.stem.split("_")
    return parcalar[1] if len(parcalar) > 1 else "?"


def etiket_sayilarini_topla(goruntuler: list[Path], etiket_dizin: Path) -> dict[Path, int]:
    """Her goruntunun etiket kutusu sayisini dondurur; goruntuyu acmaz, sadece
    etiket dosyasindaki gecerli satirlari sayar, bu yuzden cok hizlidir."""
    sayimlar: dict[Path, int] = {}
    for yol in goruntuler:
        dosya = etiket_yolu(yol, etiket_dizin)
        if not dosya.is_file():
            sayimlar[yol] = 0
            continue
        sayimlar[yol] = sum(
            1 for satir in dosya.read_text(encoding="utf-8").splitlines()
            if len(satir.split()) >= 5
        )
    return sayimlar


def tabakali_sec(sayimlar: dict[Path, int]) -> list[tuple[str, Path, int]]:
    """Goruntuleri kalabalik / az etiketli / negatif olmak uzere uc tabakadan
    secer ve (grup, yol, etiket_sayisi) listesi dondurur. Siralamalar ada gore
    sabitlenmistir; ayni veri icin secim her calistirmada aynidir."""
    secilenler: list[tuple[str, Path, int]] = []
    kullanilmis: set[Path] = set()

    def ekle(grup: str, adaylar: list[Path], adet: int) -> None:
        """Bir tabakadan istenen sayida goruntuyu, daha once secilmemis olanlardan alir."""
        alinan = 0
        for yol in adaylar:
            if alinan >= adet:
                break
            if yol in kullanilmis:
                continue
            kullanilmis.add(yol)
            secilenler.append((grup, yol, sayimlar[yol]))
            alinan += 1
        if alinan < adet:
            print(f"  UYARI: '{grup}' tabakasinda {adet} yerine {alinan} goruntu bulundu.")

    # Kalabalik: en cok etiketi olanlar. Esitlikte ad sirasi belirleyici.
    kalabalik = sorted(
        (y for y, n in sayimlar.items() if n > 0),
        key=lambda y: (-sayimlar[y], y.name),
    )
    ekle("kalabalik", kalabalik, KALABALIK_ADET)

    # Az etiketli: 1-2 kutulu sahneler.
    az = sorted(
        (y for y, n in sayimlar.items() if AZ_ALT_SINIR <= n <= AZ_UST_SINIR),
        key=lambda y: y.name,
    )
    ekle("az_etiketli", az, AZ_ADET)

    # Negatif: hic etiketi olmayanlar. Modelin bos arazideki yanlis pozitiflerini
    # gormek icin orneklemde kasten yer alirlar.
    negatif = sorted((y for y, n in sayimlar.items() if n == 0), key=lambda y: y.name)
    ekle("negatif", negatif, NEGATIF_ADET)

    return secilenler


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

    cizici.rectangle([x, etiket_y, x + genislik + 4, etiket_y + yukseklik + 4], fill=TAHMIN_RENK)
    cizici.text((x + 2, etiket_y + 2), metin, fill=YAZI_RENK, font=font)


def goruntuyu_isaretle(
    goruntu_yolu: Path,
    gercekler: list[Kutu],
    tahminler: list[Kutu],
    grup: str,
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
    aciklama = f"[{grup}]  YESIL = gercek ({len(gercekler)})   KIRMIZI = tahmin ({len(tahminler)})"
    aciklama_font = yazi_tipi(max(14, kucuk.width // 70))
    sol, ust, sag, alt = cizici.textbbox((0, 0), aciklama, font=aciklama_font)
    cizici.rectangle([0, 0, sag - sol + 12, alt - ust + 12], fill=(0, 0, 0))
    cizici.text((6, 6), aciklama, fill=YAZI_RENK, font=aciklama_font)

    hedef.parent.mkdir(parents=True, exist_ok=True)
    kucuk.save(hedef, quality=90)


def main() -> None:
    """Ornekleri tabakali secer, isaretli kopyalarini kaydeder ve secim listesini
    hem ekrana basar hem CSV'ye yazar."""
    arg = argumanlari_coz()

    goruntu_dizin, etiket_dizin = bolum_yolu(arg.bolum, arg.veri)
    goruntuler = goruntuleri_listele(goruntu_dizin)
    if arg.onek:
        secilen = {o.upper() for o in arg.onek}
        goruntuler = [y for y in goruntuler if onek_cikar(y).upper() in secilen]
    if not goruntuler:
        raise SystemExit(
            f"'{arg.bolum}' bolumunde "
            f"{('onek filtresi ' + ','.join(arg.onek) + ' ile ') if arg.onek else ''}"
            "goruntu bulunamadi."
        )

    print(f"Bolum: {arg.bolum} | Onek: {','.join(arg.onek) if arg.onek else 'hepsi'} | "
          f"Havuz: {len(goruntuler)} goruntu | conf >= {arg.conf}")
    print(f"Tabakalar: {KALABALIK_ADET} kalabalik + {AZ_ADET} az etiketli "
          f"({AZ_ALT_SINIR}-{AZ_UST_SINIR} kutu) + {NEGATIF_ADET} negatif\n")

    sayimlar = etiket_sayilarini_topla(goruntuler, etiket_dizin)
    secilenler = tabakali_sec(sayimlar)

    model = model_kur(arg.model, arg.conf)
    arg.cikti.mkdir(parents=True, exist_ok=True)

    satirlar: list[dict] = []
    for sira, (grup, yol, etiket_sayisi) in enumerate(
        tqdm(secilenler, desc="cizim", unit="gor"), start=1
    ):
        with Image.open(yol) as gorsel:
            genislik, yukseklik = gorsel.size
        gercekler = yolo_etiket_oku(etiket_yolu(yol, etiket_dizin), genislik, yukseklik)
        tahminler = [
            k for k in karolamali_tara(model, yol, arg.karo, arg.ortusme)
            if k.skor >= arg.conf
        ]
        eslesmeler, _, eslesmeyen_tahmin = kutulari_eslestir(gercekler, tahminler, arg.iou)

        hedef = arg.cikti / f"{sira:02d}_{grup}_{yol.stem[:36]}.jpg"
        goruntuyu_isaretle(yol, gercekler, tahminler, grup, arg.maks_kenar, hedef)

        satirlar.append({
            "sira": sira,
            "grup": grup,
            "kaynak_onek": onek_cikar(yol),
            "goruntu": yol.name,
            "etiket_sayisi": etiket_sayisi,
            "tahmin_sayisi": len(tahminler),
            "eslesen": len(eslesmeler),
            "yanlis_pozitif": len(eslesmeyen_tahmin),
            "cikti_dosyasi": hedef.name,
        })

    kosu = kosu_bilgisi(
        model=arg.model,
        bolum=arg.bolum,
        onek_filtresi=",".join(arg.onek) if arg.onek else "hepsi",
        havuz_goruntu_sayisi=len(goruntuler),
        kalabalik_adet=KALABALIK_ADET,
        az_etiketli_adet=AZ_ADET,
        az_etiketli_araligi=f"{AZ_ALT_SINIR}-{AZ_UST_SINIR}",
        negatif_adet=NEGATIF_ADET,
        karo_boyutu=arg.karo,
        ortusme_orani=arg.ortusme,
        conf_esigi=arg.conf,
        iou_esigi=arg.iou,
        maks_kenar=arg.maks_kenar,
    )
    hedef_csv = csv_yaz(arg.secim_csv, satirlar, kosu)

    print("\n=== SECILEN ORNEKLER ===")
    tablo_bas(satirlar, ["sira", "grup", "kaynak_onek", "etiket_sayisi",
                         "tahmin_sayisi", "eslesen", "yanlis_pozitif", "goruntu"])
    print(f"\nGoruntuler: {arg.cikti}")
    print(f"Secim listesi: {hedef_csv}")


if __name__ == "__main__":
    main()
