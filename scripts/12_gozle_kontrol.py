"""Karolanmis egitim kumesinden secilmis karolari etiket kutulariyla cizer.

Kutular, karolama mantigi yeniden hesaplanarak degil, diskteki YOLO etiket
dosyalarindan okunarak cizilir. Dogrulanmasi gereken sey uretilen dosyalarin
kendisidir; geometriyi tekrar hesaplayip cizmek, ayni hatayi iki kez yapip
tutarli gorunmesinden ibaret olurdu.

Secim rastgele degil kasitlidir: koordinat kaymasi en once kirpilmis kutularda,
olcek hatasi en once uc boyutlarda gorunur.
"""

from __future__ import annotations

import argparse
import importlib.util
import random
import sys
from pathlib import Path

SCRIPT_DIZIN = Path(__file__).resolve().parent
PROJE_KOK = SCRIPT_DIZIN.parent
sys.path.insert(0, str(SCRIPT_DIZIN))
sys.path.insert(0, str(PROJE_KOK / "backend"))

from ortak import RAPOR_KOK, VERI_KOK, bolum_yolu, etiket_yolu, goruntuleri_listele, yolo_etiket_oku  # noqa: E402
from core.tiling import karolari_hesapla  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "karo_veri", SCRIPT_DIZIN / "11_karo_veri_hazirla.py"
)
karo_veri = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(karo_veri)

TOHUM = 0

# (kategori, aciklama, kac tane). Sira dosya adina yansir.
KATEGORILER = [
    ("kirpik", "gorunur oran 0,60-0,75: kenar kuralini ancak gecmis kirpilmis kutu", 3),
    ("buyuk", "kutu yuksekligi > 150 px", 3),
    ("medyan", "kutu yuksekligi 55-65 px (medyan 59 px civari)", 3),
    ("coklu", "karoda birden fazla etiket", 1),
]

KUTU_RENGI = (0, 255, 0)


def argumanlari_coz() -> argparse.Namespace:
    ayrastirici = argparse.ArgumentParser(
        description="Karolanmis egitim kumesinden kasitli secilmis karolari etiketleriyle cizer.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--karo", type=int, default=320, help="Hangi karo kumesi kontrol edilecek")
    ayrastirici.add_argument("--ortusme", type=float, default=None, help="Kume uretilirken kullanilan ortusme orani")
    ayrastirici.add_argument("--min-gorunur", type=float, default=0.6, help="Kume uretilirken kullanilan gorunurluk esigi")
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Kaynak veri kumesi kok klasoru")
    ayrastirici.add_argument("--kume", type=Path, default=None, help="Karo kumesi dizini (varsayilan: data/karo_<karo>)")
    ayrastirici.add_argument("--cikti", type=Path, default=None, help="PNG cikti dizini")
    return ayrastirici.parse_args()


def adaylari_topla(veri_kok: Path, karo: int, ortusme: float, min_gorunur: float) -> dict:
    """Pozitif karolari gezip her kategori icin aday listesi cikarir."""
    from PIL import Image

    adaylar = {ad: [] for ad, _, _ in KATEGORILER}

    for kaynak_bolum, yolo_bolum in karo_veri.BOLUM_ESLESMESI.items():
        goruntu_dizin, etiket_dizin = bolum_yolu(kaynak_bolum, veri_kok)
        for yol in goruntuleri_listele(goruntu_dizin):
            with Image.open(yol) as gorsel:
                genislik, yukseklik = gorsel.size
            nesneler = yolo_etiket_oku(etiket_yolu(yol, etiket_dizin), genislik, yukseklik)
            if not nesneler:
                continue
            kutular = [(k.x1, k.y1, k.x2, k.y2) for k in nesneler]

            for satir, sutun, x1, y1, x2, y2 in karolari_hesapla(genislik, yukseklik, karo, ortusme):
                karo_kutusu = (x1, y1, x2, y2)
                gecen = []
                for nesne, kutu in zip(nesneler, kutular):
                    oran = karo_veri.gorunur_oran(kutu, karo_kutusu)
                    if oran >= min_gorunur:
                        gecen.append((oran, nesne))
                if not gecen:
                    continue

                kayit = (yolo_bolum, yol.stem, satir, sutun, len(gecen))
                if any(0.60 <= o <= 0.75 for o, _ in gecen):
                    adaylar["kirpik"].append(kayit)
                if any(n.yukseklik > 150 for _, n in gecen):
                    adaylar["buyuk"].append(kayit)
                if any(55 <= n.yukseklik <= 65 for _, n in gecen):
                    adaylar["medyan"].append(kayit)
                if len(gecen) > 1:
                    adaylar["coklu"].append(kayit)
    return adaylar


def sec(adaylar: dict) -> list[tuple]:
    """Her kategoriden istenen sayida karo secer; ayni karo iki kategoriye girmez."""
    secilen: list[tuple] = []
    kullanilan: set = set()
    for ad, _, kac in KATEGORILER:
        havuz = [k for k in sorted(adaylar[ad]) if k not in kullanilan]
        if not havuz:
            print(f"  UYARI: '{ad}' kategorisinde aday yok.")
            continue
        if len(havuz) < kac:
            print(f"  UYARI: '{ad}' kategorisinde {kac} degil {len(havuz)} aday var.")
        # Sabit tohumla ornekleme: farkli kaynak goruntulerden gelme sansi,
        # listenin basindan almaya gore daha yuksek.
        alinan = sorted(random.Random(TOHUM).sample(havuz, min(kac, len(havuz))))
        for kayit in alinan:
            kullanilan.add(kayit)
            secilen.append((ad, *kayit))
    return secilen


def ciz(secilen: list[tuple], kume: Path, cikti: Path) -> list[Path]:
    """Secilen karolari diskteki etiket dosyalarindan okuyup kutulariyla cizer."""
    from PIL import Image, ImageDraw

    cikti.mkdir(parents=True, exist_ok=True)
    yazilan: list[Path] = []

    for kategori, yolo_bolum, kaynak_stem, satir, sutun, _ in secilen:
        ad = f"{kaynak_stem}_r{satir:02d}_c{sutun:02d}"
        karo_yolu = kume / "images" / yolo_bolum / f"{ad}.jpg"
        etiket = kume / "labels" / yolo_bolum / f"{ad}.txt"
        if not karo_yolu.is_file():
            print(f"  UYARI: karo bulunamadi, atlandi: {karo_yolu}")
            continue

        gorsel = Image.open(karo_yolu).convert("RGB")
        genislik, yukseklik = gorsel.size
        cizici = ImageDraw.Draw(gorsel)

        kutu_sayisi = 0
        for metin in etiket.read_text(encoding="utf-8").splitlines():
            parcalar = metin.split()
            if len(parcalar) < 5:
                continue
            _, xm, ym, g, y = (float(p) for p in parcalar[:5])
            # Normalize YOLO degerini karo pikseline geri cevir. Bu cevrim
            # uretimdekinin tersidir; kutu nesnenin uzerine oturmuyorsa hata
            # uretim tarafindadir.
            cizici.rectangle(
                [
                    (xm - g / 2) * genislik, (ym - y / 2) * yukseklik,
                    (xm + g / 2) * genislik, (ym + y / 2) * yukseklik,
                ],
                outline=KUTU_RENGI, width=1,
            )
            kutu_sayisi += 1

        hedef = cikti / f"{kategori}_{ad}_n{kutu_sayisi}.png"
        gorsel.save(hedef)
        yazilan.append(hedef)
    return yazilan


def main() -> None:
    arg = argumanlari_coz()
    ortusme = karo_veri.ortusmeyi_sec(arg.karo, arg.ortusme)
    kume = arg.kume or (PROJE_KOK / "data" / f"karo_{arg.karo}")
    cikti = arg.cikti or (RAPOR_KOK / f"gozle_kontrol_{arg.karo}")

    if not kume.is_dir():
        raise SystemExit(f"Karo kumesi bulunamadi: {kume}")

    print(f"Kume: {kume} | karo {arg.karo} | ortusme {ortusme}")
    adaylar = adaylari_topla(arg.veri, arg.karo, ortusme, arg.min_gorunur)
    for ad, aciklama, _ in KATEGORILER:
        print(f"  {ad:>7}: {len(adaylar[ad])} aday  ({aciklama})")

    yazilan = ciz(sec(adaylar), kume, cikti)
    print(f"\n{len(yazilan)} PNG yazildi:")
    for yol in yazilan:
        print(f"  {yol}")


if __name__ == "__main__":
    main()
