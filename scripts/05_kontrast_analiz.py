"""Her gercek kutu icin, kutunun ici ile kutuyu cevreleyen halka arasindaki
parlaklik farkini (yerel kontrast) olcer ve kaynak bazinda medyanini cikarir.
Sonucu recall ve kutu boyutuyla ayni tabloda birlestirerek, dusuk recall'in
boyuttan mi yoksa kontrasttan mi kaynaklandigini ayirt etmeye calisir.
Model taramasi yapmaz."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from tqdm import tqdm

from ortak import (
    RAPOR_KOK,
    VERI_KOK,
    Kutu,
    bolum_yolu,
    csv_yaz,
    etiket_yolu,
    goruntuleri_listele,
    kosu_bilgisi,
    sayi_bicimle,
    tablo_bas,
    yolo_etiket_oku,
)

TUM_BOLUMLER = ["train", "valid", "test"]
# Halka, kutunun bu katsayiyla genisletilmis halinden kutunun kendisi cikarilarak
# elde edilir. 3 kat, insanin hemen cevresindeki arka plani kapsar ama sahnenin
# tamamina yayilmayacak kadar dardir.
HALKA_KATSAYISI = 3.0
GRAFIK_CONF = "0.3"


def argumanlari_coz() -> argparse.Namespace:
    """Komut satiri argumanlarini tanimlar ve cozer."""
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Her etiket kutusunun ic parlakligi ile cevresindeki halkanin "
            "parlakligi arasindaki farki olcer ve kaynak bazinda medyanini "
            "reports/onek_kontrast.csv olarak kaydeder. Sonuc, kutu boyutu ve "
            "recall ile ayni tabloda birlestirilir. Model calistirmaz."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Veri kumesi kok klasoru")
    ayrastirici.add_argument("--bolum", nargs="+", default=TUM_BOLUMLER, help="Taranacak bolumler")
    ayrastirici.add_argument(
        "--kutu-boyutu", type=Path, default=RAPOR_KOK / "onek_kutu_boyutu.csv",
        help="Kutu boyutu ve recall degerlerinin okunacagi CSV (04 uretir)",
    )
    ayrastirici.add_argument("--cikti", type=Path, default=RAPOR_KOK / "onek_kontrast.csv", help="Sonuc CSV yolu")
    return ayrastirici.parse_args()


def onek_cikar(goruntu: Path) -> str:
    """Dosya adindan kaynak onegini cikarir: train_BLI_0004_... -> BLI"""
    parcalar = goruntu.stem.split("_")
    return parcalar[1] if len(parcalar) > 1 else "?"


def kutu_kontrasti(gri: np.ndarray, kutu: Kutu) -> tuple[float, float] | None:
    """Bir kutunun ic parlakligi ile cevresindeki halkanin parlakligini olcer ve
    (isaretli fark, ic parlaklik) dondurur. Halka, genisletilmis kutudan ic kutu
    cikarilarak hesaplanir; gecerli piksel kalmazsa None doner."""
    yukseklik, genislik = gri.shape

    # Ic bolge; goruntu sinirlarina kirpilir.
    ix1, iy1 = max(0, int(kutu.x1)), max(0, int(kutu.y1))
    ix2, iy2 = min(genislik, int(math.ceil(kutu.x2))), min(yukseklik, int(math.ceil(kutu.y2)))
    if ix2 <= ix1 or iy2 <= iy1:
        return None

    # Dis bolge: ayni merkez, kenarlari HALKA_KATSAYISI kat buyuk.
    merkez_x, merkez_y = (kutu.x1 + kutu.x2) / 2, (kutu.y1 + kutu.y2) / 2
    yari_g = kutu.genislik * HALKA_KATSAYISI / 2
    yari_y = kutu.yukseklik * HALKA_KATSAYISI / 2
    dx1, dy1 = max(0, int(merkez_x - yari_g)), max(0, int(merkez_y - yari_y))
    dx2 = min(genislik, int(math.ceil(merkez_x + yari_g)))
    dy2 = min(yukseklik, int(math.ceil(merkez_y + yari_y)))
    if dx2 <= dx1 or dy2 <= dy1:
        return None

    ic = gri[iy1:iy2, ix1:ix2]
    dis = gri[dy1:dy2, dx1:dx2]

    ic_piksel = ic.size
    dis_piksel = dis.size
    halka_piksel = dis_piksel - ic_piksel
    if ic_piksel == 0 or halka_piksel <= 0:
        return None

    # Halka ortalamasi, toplamlarin farkindan cikarilir; halkayi ayrica maskelemek
    # gerekmez, bu da bellek ve zaman kazandirir.
    ic_ortalama = float(ic.mean())
    halka_ortalama = (float(dis.sum()) - float(ic.sum())) / halka_piksel
    return ic_ortalama - halka_ortalama, ic_ortalama


def kontrastlari_topla(bolumler: list[str], veri_kok: Path) -> pd.DataFrame:
    """Tum etiketli goruntuleri gezip her kutunun kontrast olcumunu toplar.
    Her goruntu yalnizca bir kez ve gri tonlamali olarak acilir; etiketi olmayan
    goruntuler hic acilmaz."""
    kayitlar: list[dict] = []
    for bolum in bolumler:
        goruntu_dizin, etiket_dizin = bolum_yolu(bolum, veri_kok)
        goruntuler = goruntuleri_listele(goruntu_dizin)
        for yol in tqdm(goruntuler, desc=f"{bolum:5}", unit="gor", leave=False):
            etiket_dosya = etiket_yolu(yol, etiket_dizin)
            # Once etiket dosyasina bakiyoruz; kutusu olmayan goruntuyu acmaya
            # gerek yok, bu da sureyi belirgin sekilde kisaltiyor.
            if not etiket_dosya.is_file():
                continue
            if not any(len(s.split()) >= 5 for s in etiket_dosya.read_text(encoding="utf-8").splitlines()):
                continue

            with Image.open(yol) as gorsel:
                genislik, yukseklik = gorsel.size
                gri = np.asarray(gorsel.convert("L"), dtype=np.float32)

            for kutu in yolo_etiket_oku(etiket_dosya, genislik, yukseklik):
                sonuc = kutu_kontrasti(gri, kutu)
                if sonuc is None:
                    continue
                fark, ic_parlaklik = sonuc
                kayitlar.append({
                    "onek": onek_cikar(yol),
                    "goruntu": yol.name,
                    "kutu_kenar_px": math.sqrt(kutu.alan),
                    "kontrast_isaretli": fark,
                    "kontrast_mutlak": abs(fark),
                    "ic_parlaklik": ic_parlaklik,
                })
    return pd.DataFrame(kayitlar)


def boyut_modeli_artigi(kenarlar: np.ndarray, recaller: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Recall'i yalnizca kutu boyutundan tahmin eden dogrusal modeli kurar ve her
    kaynagin bu modelden sapmasini (artik) dondurur. Artik negatifse kaynak,
    kutu boyutunun ongordugunden daha kotu demektir."""
    egim, kesme = np.polyfit(kenarlar, recaller, 1)
    return recaller - (egim * kenarlar + kesme), float(egim), float(kesme)


def korelasyon(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Pearson ve Spearman korelasyon katsayilarini dondurur."""
    pearson = float(np.corrcoef(x, y)[0, 1])
    sira_x = np.argsort(np.argsort(x)).astype(float)
    sira_y = np.argsort(np.argsort(y)).astype(float)
    return pearson, float(np.corrcoef(sira_x, sira_y)[0, 1])


def main() -> None:
    """Kontrastlari olcer, kutu boyutu ve recall ile birlestirir, tabloyu basar."""
    arg = argumanlari_coz()

    if not arg.kutu_boyutu.is_file():
        raise SystemExit(
            f"Kutu boyutu dosyasi bulunamadi: {arg.kutu_boyutu}\n"
            "Once su komutu calistirin:\n"
            "  .venv/bin/python scripts/04_kutu_boyutu_analiz.py"
        )

    print(f"Bolumler: {'+'.join(arg.bolum)} | Model taramasi YOK")
    print(f"Halka: kutunun {HALKA_KATSAYISI:g} katina genisletilmis alanindan kutunun kendisi cikarilir\n")

    olcumler = kontrastlari_topla(arg.bolum, arg.veri)
    if olcumler.empty:
        raise SystemExit("Hic kutu olculemedi.")

    # 04'un urettigi kaynak bazli boyut/recall tablosunu okuyup birlestiriyoruz.
    boyut_tablosu = {
        s["kaynak_onek"]: s
        for s in csv.DictReader(arg.kutu_boyutu.open(encoding="utf-8"))
    }

    satirlar: list[dict] = []
    for onek, grup in olcumler.groupby("onek"):
        kaynak = boyut_tablosu.get(onek, {})
        recall = kaynak.get(f"recall_conf{GRAFIK_CONF}", "")
        satirlar.append({
            "kaynak_onek": onek,
            "kutu_sayisi": len(grup),
            "medyan_kutu_kenar_px": sayi_bicimle(grup["kutu_kenar_px"].median(), 1),
            "medyan_kontrast_mutlak": sayi_bicimle(grup["kontrast_mutlak"].median(), 2),
            "medyan_kontrast_isaretli": sayi_bicimle(grup["kontrast_isaretli"].median(), 2),
            "medyan_ic_parlaklik": sayi_bicimle(grup["ic_parlaklik"].median(), 1),
            f"recall_conf{GRAFIK_CONF}": float(recall) if recall else "",
        })

    # Boyut modelinden artik: recall'in yalnizca boyutla aciklanamayan kismi.
    gecerli = [s for s in satirlar if s[f"recall_conf{GRAFIK_CONF}"] != ""]
    kenarlar = np.array([s["medyan_kutu_kenar_px"] for s in gecerli])
    recaller = np.array([s[f"recall_conf{GRAFIK_CONF}"] for s in gecerli])
    artiklar, egim, kesme = boyut_modeli_artigi(kenarlar, recaller)
    for satir, artik in zip(gecerli, artiklar):
        satir["boyut_modelinden_artik"] = sayi_bicimle(artik, 4)
    for satir in satirlar:
        satir.setdefault("boyut_modelinden_artik", "")

    satirlar.sort(key=lambda s: s["boyut_modelinden_artik"] if s["boyut_modelinden_artik"] != "" else 0)

    kontrastlar = np.array([s["medyan_kontrast_mutlak"] for s in gecerli])
    kon_artik_p, kon_artik_s = korelasyon(kontrastlar, artiklar)
    kon_recall_p, kon_recall_s = korelasyon(kontrastlar, recaller)

    kosu = kosu_bilgisi(
        bolumler="+".join(arg.bolum),
        halka_katsayisi=HALKA_KATSAYISI,
        olculen_kutu=len(olcumler),
        kaynak_sayisi=len(satirlar),
        recall_conf_esigi=GRAFIK_CONF,
        boyut_modeli=f"recall = {egim:.5f} * kenar + {kesme:.5f}",
        kontrast_artik_pearson=round(kon_artik_p, 4),
        kontrast_artik_spearman=round(kon_artik_s, 4),
        kontrast_recall_pearson=round(kon_recall_p, 4),
        not_="model taramasi yapilmadi; kontrast gri tonlamali pikselden olculdu",
    )
    hedef = csv_yaz(arg.cikti, satirlar, kosu)

    print("=== KAYNAK BAZINDA KONTRAST ve RECALL (artiga gore sirali) ===")
    tablo_bas(satirlar, ["kaynak_onek", "kutu_sayisi", "medyan_kutu_kenar_px",
                         "medyan_kontrast_mutlak", "medyan_kontrast_isaretli",
                         f"recall_conf{GRAFIK_CONF}", "boyut_modelinden_artik"])

    print("\n=== KORELASYON ===")
    print(f"  kontrast vs boyut-modeli-artigi : r={kon_artik_p:+.4f}  rho={kon_artik_s:+.4f}")
    print(f"  kontrast vs recall (ham)        : r={kon_recall_p:+.4f}  rho={kon_recall_s:+.4f}")
    print(f"\nOlculen kutu: {len(olcumler)}")
    print(f"CSV kaydedildi: {hedef}")


if __name__ == "__main__":
    main()
