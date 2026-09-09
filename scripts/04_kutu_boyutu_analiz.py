"""Her kaynak (onek) icin etiket kutusu boyutu istatistiklerini cikarir ve bunlari
taban_cizgisi_onek.csv icindeki recall degerleriyle ayni tabloda birlestirir. Model
taramasi yapmaz; sadece etiket dosyalarini ve goruntu basliklarini okur. Ayrica
recall ile kutu boyutu iliskisini gosteren bir dagilim grafigi cizer."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Ekran olmadan PNG uretmek icin.
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

from ortak import (
    RAPOR_KOK,
    VERI_KOK,
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
GRAFIK_CONF = "0.3"  # Grafikte kullanilan guven esigi.

# Renkler dataviz referans paletinden; tek serilik dagilim grafigi icin tek hue.
ZEMIN = "#fcfcfb"
NOKTA = "#2a78d6"
ANA_YAZI = "#0b0b0b"
IKINCIL_YAZI = "#52514e"
SOLUK = "#898781"
IZGARA = "#e1e0d9"


def argumanlari_coz() -> argparse.Namespace:
    """Komut satiri argumanlarini tanimlar ve cozer."""
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Kaynak (onek) bazinda etiket kutusu boyutu istatistiklerini hesaplar ve "
            "taban cizgisi recall degerleriyle birlestirir. Model calistirmaz. "
            "Ciktilar: reports/onek_kutu_boyutu.csv ve "
            "reports/recall_vs_kutu_boyutu.png"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Veri kumesi kok klasoru")
    ayrastirici.add_argument("--bolum", nargs="+", default=TUM_BOLUMLER, help="Taranacak bolumler")
    ayrastirici.add_argument(
        "--taban-cizgisi", type=Path, default=RAPOR_KOK / "taban_cizgisi_onek.csv",
        help="Recall degerlerinin okunacagi kaynak bazli taban cizgisi CSV'si",
    )
    ayrastirici.add_argument("--cikti", type=Path, default=RAPOR_KOK / "onek_kutu_boyutu.csv", help="Sonuc CSV yolu")
    ayrastirici.add_argument("--grafik", type=Path, default=RAPOR_KOK / "recall_vs_kutu_boyutu.png", help="Grafik PNG yolu")
    return ayrastirici.parse_args()


def onek_cikar(goruntu: Path) -> str:
    """Dosya adindan kaynak onegini cikarir: train_ZRI_3035_... -> ZRI"""
    parcalar = goruntu.stem.split("_")
    return parcalar[1] if len(parcalar) > 1 else "?"


def kutu_olcumlerini_topla(bolumler: list[str], veri_kok: Path) -> pd.DataFrame:
    """Tum bolumlerdeki etiket kutularini kaynak onegiyle birlikte piksel olcumleri
    halinde toplar. Goruntu pikselleri cozulmez, sadece basliktan boyut okunur."""
    kayitlar: list[dict] = []
    for bolum in bolumler:
        goruntu_dizin, etiket_dizin = bolum_yolu(bolum, veri_kok)
        for yol in goruntuleri_listele(goruntu_dizin):
            with Image.open(yol) as gorsel:
                genislik, yukseklik = gorsel.size
            for kutu in yolo_etiket_oku(etiket_yolu(yol, etiket_dizin), genislik, yukseklik):
                kayitlar.append({
                    "onek": onek_cikar(yol),
                    "kutu_genislik": kutu.genislik,
                    "kutu_yukseklik": kutu.yukseklik,
                    "kutu_alan": kutu.alan,
                })
    return pd.DataFrame(kayitlar)


def goruntu_sayilari(bolumler: list[str], veri_kok: Path) -> dict[str, int]:
    """Kaynak basina goruntu sayisini dondurur (etiketi olmayanlar dahil)."""
    sayim: dict[str, int] = defaultdict(int)
    for bolum in bolumler:
        goruntu_dizin, _ = bolum_yolu(bolum, veri_kok)
        for yol in goruntuleri_listele(goruntu_dizin):
            sayim[onek_cikar(yol)] += 1
    return dict(sayim)


def recall_oku(yol: Path) -> dict[tuple[str, str], dict[str, str]]:
    """Kaynak bazli taban cizgisi CSV'sini (onek, conf) anahtariyla okur."""
    if not yol.is_file():
        raise SystemExit(
            f"Taban cizgisi dosyasi bulunamadi: {yol}\n"
            "Once su komutu calistirin:\n"
            "  .venv/bin/python scripts/01_taban_cizgisi.py --bolum hepsi "
            "--limit 0 --onek-bazinda --cikti reports/taban_cizgisi_onek.csv"
        )
    return {
        (s["kaynak_onek"], s["conf_esigi"]): s
        for s in csv.DictReader(yol.open(encoding="utf-8"))
    }


def tabloyu_kur(
    olcumler: pd.DataFrame, gor_sayilari: dict[str, int], recaller: dict
) -> list[dict]:
    """Kutu boyutu istatistiklerini recall degerleriyle birlestirip kaynak basina
    tek satirlik bir tablo uretir; satirlar kutu sayisina gore azalan siralanir."""
    satirlar: list[dict] = []
    for onek, grup in olcumler.groupby("onek"):
        medyan_alan = float(grup["kutu_alan"].median())
        satir = {
            "kaynak_onek": onek,
            "goruntu_sayisi": gor_sayilari.get(onek, 0),
            "kutu_sayisi": len(grup),
            "medyan_genislik_px": sayi_bicimle(grup["kutu_genislik"].median(), 1),
            "medyan_yukseklik_px": sayi_bicimle(grup["kutu_yukseklik"].median(), 1),
            "medyan_alan_px2": sayi_bicimle(medyan_alan, 1),
            # Kenar uzunlugu = alanin karekoku; genislik ve yuksekligi tek bir
            # karsilastirilabilir sayida birlestirir, grafigin x ekseni budur.
            "medyan_kenar_px": sayi_bicimle(math.sqrt(medyan_alan), 1),
        }
        for conf in ("0.05", "0.15", "0.3"):
            kayit = recaller.get((onek, conf))
            satir[f"recall_conf{conf}"] = float(kayit["recall"]) if kayit else ""
        kayit30 = recaller.get((onek, GRAFIK_CONF))
        satir["fp_goruntu_basina_conf0.3"] = float(kayit30["fp_goruntu_basina"]) if kayit30 else ""
        satirlar.append(satir)

    satirlar.sort(key=lambda s: (-s["kutu_sayisi"], s["kaynak_onek"]))
    return satirlar


def korelasyon(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Pearson (dogrusal) ve Spearman (sirali) korelasyon katsayilarini dondurur."""
    pearson = float(np.corrcoef(x, y)[0, 1])
    # Spearman = siralamalar uzerindeki Pearson.
    sira_x = np.argsort(np.argsort(x)).astype(float)
    sira_y = np.argsort(np.argsort(y)).astype(float)
    spearman = float(np.corrcoef(sira_x, sira_y)[0, 1])
    return pearson, spearman


def etiketleri_yerlestir(eksen, fig, noktalar) -> None:
    """Kaynak adlarini noktalarin cevresine, birbirleriyle cakismayacak sekilde
    yerlestirir. Her nokta icin sirayla ust/alt/sag/sol adaylari denenir ve daha
    once yerlesmis etiketlerle kesismeyen ilk konum secilir."""
    fig.canvas.draw()  # Metin kutularinin gercek boyutu ancak cizimden sonra bilinir.
    yerlesmis = []

    # Buyuk noktalarin etiketi daha uzaga konmali; yaricap kadar bosluk birakiyoruz.
    for xi, yi, ai, ad in sorted(noktalar, key=lambda n: -n[2]):
        bosluk = 6 + math.sqrt(ai) / 2
        adaylar = [
            (0, bosluk, "center", "bottom"),
            (0, -bosluk, "center", "top"),
            (bosluk, 0, "left", "center"),
            (-bosluk, 0, "right", "center"),
            (bosluk * 0.7, bosluk * 0.7, "left", "bottom"),
            (-bosluk * 0.7, bosluk * 0.7, "right", "bottom"),
            (bosluk * 0.7, -bosluk * 0.7, "left", "top"),
            (-bosluk * 0.7, -bosluk * 0.7, "right", "top"),
        ]
        for dx, dy, yatay, dikey in adaylar:
            etiket = eksen.annotate(
                ad, (xi, yi), textcoords="offset points", xytext=(dx, dy),
                ha=yatay, va=dikey, fontsize=9.5, color=ANA_YAZI, zorder=4,
            )
            kutu = etiket.get_window_extent(fig.canvas.get_renderer())
            # 2 piksellik pay birakarak kesisim kontrolu yapiyoruz.
            genisletilmis = kutu.expanded(1.05, 1.15)
            if not any(genisletilmis.overlaps(o) for o in yerlesmis):
                yerlesmis.append(genisletilmis)
                break
            etiket.remove()
        else:
            # Hicbir aday bos degilse ilk konuma birak; hic etiket kaybetmemek daha iyi.
            etiket = eksen.annotate(
                ad, (xi, yi), textcoords="offset points", xytext=(0, bosluk),
                ha="center", va="bottom", fontsize=9.5, color=ANA_YAZI, zorder=4,
            )
            yerlesmis.append(etiket.get_window_extent(fig.canvas.get_renderer()))


def grafik_ciz(satirlar: list[dict], hedef: Path, pearson: float, spearman: float) -> Path:
    """Recall ile medyan kutu boyutu iliskisini dagilim grafigi olarak cizer; nokta
    alani kutu sayisiyla, konumu boyut ve recall ile belirlenir."""
    gecerli = [s for s in satirlar if s[f"recall_conf{GRAFIK_CONF}"] != ""]
    x = np.array([s["medyan_kenar_px"] for s in gecerli])
    y = np.array([s[f"recall_conf{GRAFIK_CONF}"] for s in gecerli])
    n = np.array([s["kutu_sayisi"] for s in gecerli], dtype=float)

    # Nokta ALANI kutu sayisiyla orantili; goz alani algiladigi icin yaricapa degil
    # alana esleniyor. 40-900 araligi kucuk kaynaklari da gorunur tutuyor.
    alan = 40 + 860 * (n - n.min()) / (n.max() - n.min()) if n.max() > n.min() else np.full_like(n, 200)

    fig, eksen = plt.subplots(figsize=(10.5, 7.2), facecolor=ZEMIN)
    eksen.set_facecolor(ZEMIN)

    # Egilim cizgisi once cizilir ki noktalarin altinda kalsin.
    if len(x) > 2:
        egim, kesme = np.polyfit(x, y, 1)
        xs = np.linspace(x.min() * 0.95, x.max() * 1.05, 50)
        eksen.plot(xs, egim * xs + kesme, color=SOLUK, linewidth=2,
                   linestyle="--", zorder=1, alpha=0.8)

    eksen.scatter(x, y, s=alan, color=NOKTA, alpha=0.55, zorder=3,
                  edgecolors=ZEMIN, linewidths=2)

    eksen.set_xlabel("Medyan kutu kenari  (√alan, piksel)", fontsize=11, color=IKINCIL_YAZI)
    eksen.set_ylabel(f"Recall  (conf = {GRAFIK_CONF})", fontsize=11, color=IKINCIL_YAZI)
    eksen.set_title(
        "Kaynak bazinda recall ile etiket kutusu boyutu iliskisi",
        fontsize=13.5, color=ANA_YAZI, pad=34, loc="left",
    )
    eksen.text(
        0, 1.012,
        f"Her nokta bir kaynak; nokta alani kutu sayisiyla orantili.  "
        f"Pearson r = {pearson:.2f},  Spearman rho = {spearman:.2f}",
        transform=eksen.transAxes, fontsize=9.5, color=SOLUK,
    )

    eksen.grid(True, color=IZGARA, linewidth=1, zorder=0)
    eksen.set_axisbelow(True)
    for kenar in ("top", "right"):
        eksen.spines[kenar].set_visible(False)
    for kenar in ("left", "bottom"):
        eksen.spines[kenar].set_color(IZGARA)
    eksen.tick_params(colors=SOLUK, labelsize=9.5)

    # Nokta buyuklugunun ne anlama geldigini gosteren kucuk bir olcek aciklamasi.
    for referans in (int(n.min()), int(n.max())):
        olcek = 40 + 860 * (referans - n.min()) / (n.max() - n.min()) if n.max() > n.min() else 200
        eksen.scatter([], [], s=olcek, color=NOKTA, alpha=0.55,
                      edgecolors=ZEMIN, linewidths=2, label=f"{referans} kutu")
    aciklama = eksen.legend(
        title="Kaynaktaki kutu sayisi", loc="upper left", frameon=False,
        labelspacing=1.6, borderpad=1.0, fontsize=9.5,
    )
    aciklama.get_title().set_color(IKINCIL_YAZI)
    aciklama.get_title().set_fontsize(9.5)
    for metin in aciklama.get_texts():
        metin.set_color(IKINCIL_YAZI)

    # Etiketler en son yerlestirilir: eksen sinirlari ve nokta konumlari kesinlesmis
    # olmali ki cakisma hesabi gercek piksel konumlari uzerinden yapilabilsin.
    fig.tight_layout()
    etiketleri_yerlestir(eksen, fig, list(zip(x, y, alan, [s["kaynak_onek"] for s in gecerli])))

    hedef.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(hedef, dpi=150, facecolor=ZEMIN)
    plt.close(fig)
    return hedef


def main() -> None:
    """Kutu olcumlerini toplar, recall ile birlestirir, tabloyu ve grafigi uretir."""
    arg = argumanlari_coz()

    print(f"Bolumler: {'+'.join(arg.bolum)} | Model taramasi YOK, sadece etiket okunuyor\n")
    olcumler = kutu_olcumlerini_topla(arg.bolum, arg.veri)
    gor_sayilari = goruntu_sayilari(arg.bolum, arg.veri)
    recaller = recall_oku(arg.taban_cizgisi)
    satirlar = tabloyu_kur(olcumler, gor_sayilari, recaller)

    gecerli = [s for s in satirlar if s[f"recall_conf{GRAFIK_CONF}"] != ""]
    x = np.array([s["medyan_kenar_px"] for s in gecerli])
    y = np.array([s[f"recall_conf{GRAFIK_CONF}"] for s in gecerli])
    pearson, spearman = korelasyon(x, y)

    kosu = kosu_bilgisi(
        bolumler="+".join(arg.bolum),
        kaynak_sayisi=len(satirlar),
        toplam_kutu=len(olcumler),
        grafik_conf_esigi=GRAFIK_CONF,
        pearson_r=round(pearson, 4),
        spearman_rho=round(spearman, 4),
        taban_cizgisi_dosyasi=arg.taban_cizgisi.name,
        not_="model taramasi yapilmadi; kutu olcumleri etiket dosyalarindan",
    )
    hedef_csv = csv_yaz(arg.cikti, satirlar, kosu)
    hedef_png = grafik_ciz(satirlar, arg.grafik, pearson, spearman)

    print("=== KAYNAK BAZINDA KUTU BOYUTU ve RECALL ===")
    tablo_bas(satirlar, ["kaynak_onek", "kutu_sayisi", "medyan_genislik_px",
                         "medyan_yukseklik_px", "medyan_kenar_px",
                         "recall_conf0.05", "recall_conf0.15", "recall_conf0.3"])

    print(f"\n=== KORELASYON (medyan kutu kenari vs recall @ conf={GRAFIK_CONF}) ===")
    print(f"  Pearson  r   = {pearson:+.4f}   (dogrusal iliski)")
    print(f"  Spearman rho = {spearman:+.4f}   (sirali iliski)")

    print(f"\nCSV     : {hedef_csv}")
    print(f"Grafik  : {hedef_png}")


if __name__ == "__main__":
    main()
