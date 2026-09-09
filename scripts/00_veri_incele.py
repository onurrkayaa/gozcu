"""Veri kumesini tanimak icin temel istatistikleri hesaplar: bolum basina goruntu
sayisi, goruntu boyutlari, etiket kutusu sayilari ve kutu boyutlarinin piksel
cinsinden dagilimi. Model calistirmaz, sadece dosyalari okur."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from PIL import Image
from tqdm import tqdm

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

VARSAYILAN_BOLUMLER = ["train", "valid", "test"]


def argumanlari_coz() -> argparse.Namespace:
    """Komut satiri argumanlarini tanimlar ve cozer."""
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Veri kumesi istatistiklerini hesaplar ve reports/veri_istatistik.csv "
            "olarak kaydeder. Her bolum icin goruntu sayisi, goruntu en/boy "
            "min-medyan-maks degerleri, toplam etiket kutusu sayisi, goruntu basina "
            "ortalama kutu, kutu en/boy piksel min-medyan-maks degerleri ve kutu "
            "alaninin goruntu alanina oraninin medyani (yuzde) uretilir."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument(
        "--veri", type=Path, default=VERI_KOK,
        help="Veri kumesi kok klasoru (icinde train/valid/test bulunur)",
    )
    ayrastirici.add_argument(
        "--bolum", nargs="+", default=VARSAYILAN_BOLUMLER,
        help="Incelenecek bolumler",
    )
    ayrastirici.add_argument(
        "--cikti", type=Path, default=RAPOR_KOK / "veri_istatistik.csv",
        help="Sonuc CSV dosyasinin yolu",
    )
    ayrastirici.add_argument(
        "--onek-cikti", type=Path, default=RAPOR_KOK / "onek_dagilimi.csv",
        help="Kaynak (onek) bazli dagilimin yazilacagi CSV",
    )
    return ayrastirici.parse_args()


def onek_cikar(goruntu: Path) -> str:
    """Dosya adindan kaynak onegini cikarir: train_ZRI_3035_... -> ZRI"""
    parcalar = goruntu.stem.split("_")
    return parcalar[1] if len(parcalar) > 1 else "?"


def onek_dagilimi(bolumler: list[str], veri_kok: Path) -> list[dict]:
    """Bolum ve kaynak onegi kirilimiyla goruntu/kutu sayilarini cikarir. Veri
    kumesindeki kaynaklarin cok dengesiz dagildigini ve bolunmelerin kaynak
    bazinda ayristigini gorunur kilar; tek bir birlesik metrigin neden yaniltici
    oldugunu bu tablo belgeler."""
    from collections import defaultdict

    sayim = defaultdict(lambda: {"goruntu": 0, "kutu": 0, "bos": 0})
    for bolum in bolumler:
        goruntu_dizin, etiket_dizin = bolum_yolu(bolum, veri_kok)
        for yol in goruntuleri_listele(goruntu_dizin):
            etiket_dosya = etiket_yolu(yol, etiket_dizin)
            kutu_sayisi = 0
            if etiket_dosya.is_file():
                kutu_sayisi = sum(
                    1 for satir in etiket_dosya.read_text(encoding="utf-8").splitlines()
                    if len(satir.split()) >= 5
                )
            # Hem bolum kiriliminda hem de butun veri kumesi icin sayiyoruz.
            for anahtar in ((bolum, onek_cikar(yol)), ("HEPSI", onek_cikar(yol))):
                g = sayim[anahtar]
                g["goruntu"] += 1
                g["kutu"] += kutu_sayisi
                g["bos"] += (kutu_sayisi == 0)

    sira = {b: i for i, b in enumerate(bolumler)}
    satirlar = []
    for (bolum, onek), g in sorted(
        sayim.items(), key=lambda x: (sira.get(x[0][0], 9), -x[1]["kutu"])
    ):
        satirlar.append({
            "bolum": bolum,
            "onek": onek,
            "goruntu_sayisi": g["goruntu"],
            "kutu_sayisi": g["kutu"],
            "kutu_goruntu_basina": sayi_bicimle(g["kutu"] / g["goruntu"], 2),
            "bos_goruntu": g["bos"],
            "bos_yuzde": sayi_bicimle(100 * g["bos"] / g["goruntu"], 1),
        })
    return satirlar


def bolum_tara(bolum: str, veri_kok: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bir bolumdeki tum goruntuleri ve etiketlerini okuyup goruntu ve kutu
    olcumlerini iki ayri tabloda dondurur."""
    goruntu_dizin, etiket_dizin = bolum_yolu(bolum, veri_kok)
    goruntuler = goruntuleri_listele(goruntu_dizin)

    goruntu_kayitlari: list[dict] = []
    kutu_kayitlari: list[dict] = []

    for yol in tqdm(goruntuler, desc=f"{bolum:5}", unit="gor", leave=False):
        # PIL basligi okur, tum pikselleri cozmez; bu yuzden hizlidir.
        with Image.open(yol) as gorsel:
            genislik, yukseklik = gorsel.size

        kutular = yolo_etiket_oku(etiket_yolu(yol, etiket_dizin), genislik, yukseklik)
        goruntu_kayitlari.append(
            {"genislik": genislik, "yukseklik": yukseklik, "kutu_sayisi": len(kutular)}
        )
        goruntu_alani = genislik * yukseklik
        for kutu in kutular:
            kutu_kayitlari.append(
                {
                    "kutu_genislik": kutu.genislik,
                    "kutu_yukseklik": kutu.yukseklik,
                    "alan_orani_yuzde": 100.0 * kutu.alan / goruntu_alani,
                }
            )

    return pd.DataFrame(goruntu_kayitlari), pd.DataFrame(kutu_kayitlari)


def ozet_uret(bolum: str, goruntuler: pd.DataFrame, kutular: pd.DataFrame) -> dict:
    """Bir bolumun goruntu ve kutu tablolarindan tek satirlik ozet sozluk uretir."""

    def uc_deger(seri: pd.Series) -> tuple[float, float, float]:
        """Bos olmayan bir seriden (en kucuk, medyan, en buyuk) uclusunu cikarir."""
        if seri.empty:
            return (0.0, 0.0, 0.0)
        return (float(seri.min()), float(seri.median()), float(seri.max()))

    g_min, g_med, g_maks = uc_deger(goruntuler["genislik"])
    y_min, y_med, y_maks = uc_deger(goruntuler["yukseklik"])
    kg_min, kg_med, kg_maks = uc_deger(
        kutular["kutu_genislik"] if not kutular.empty else pd.Series(dtype=float)
    )
    ky_min, ky_med, ky_maks = uc_deger(
        kutular["kutu_yukseklik"] if not kutular.empty else pd.Series(dtype=float)
    )
    oran_medyan = (
        float(kutular["alan_orani_yuzde"].median()) if not kutular.empty else 0.0
    )

    goruntu_sayisi = len(goruntuler)
    toplam_kutu = len(kutular)

    return {
        "bolum": bolum,
        "goruntu_sayisi": goruntu_sayisi,
        "gor_genislik_min": int(g_min),
        "gor_genislik_medyan": int(g_med),
        "gor_genislik_maks": int(g_maks),
        "gor_yukseklik_min": int(y_min),
        "gor_yukseklik_medyan": int(y_med),
        "gor_yukseklik_maks": int(y_maks),
        "toplam_kutu": toplam_kutu,
        "kutu_goruntu_basina": sayi_bicimle(
            toplam_kutu / goruntu_sayisi if goruntu_sayisi else 0.0, 2
        ),
        "kutu_genislik_min_px": sayi_bicimle(kg_min, 1),
        "kutu_genislik_medyan_px": sayi_bicimle(kg_med, 1),
        "kutu_genislik_maks_px": sayi_bicimle(kg_maks, 1),
        "kutu_yukseklik_min_px": sayi_bicimle(ky_min, 1),
        "kutu_yukseklik_medyan_px": sayi_bicimle(ky_med, 1),
        "kutu_yukseklik_maks_px": sayi_bicimle(ky_maks, 1),
        "kutu_alan_orani_medyan_yuzde": sayi_bicimle(oran_medyan, 5),
    }


def main() -> None:
    """Butun bolumleri tarar, ozet tabloyu ekrana basar ve CSV'ye yazar."""
    arg = argumanlari_coz()

    satirlar: list[dict] = []
    tum_goruntuler: list[pd.DataFrame] = []
    tum_kutular: list[pd.DataFrame] = []

    for bolum in arg.bolum:
        goruntuler, kutular = bolum_tara(bolum, arg.veri)
        satirlar.append(ozet_uret(bolum, goruntuler, kutular))
        tum_goruntuler.append(goruntuler)
        tum_kutular.append(kutular)

    # Bolumleri birlestirip genel bir TOPLAM satiri ekliyoruz; boylece veri
    # kumesinin butunune dair tek bakista fikir edinilebiliyor.
    if len(arg.bolum) > 1:
        satirlar.append(
            ozet_uret(
                "TOPLAM",
                pd.concat(tum_goruntuler, ignore_index=True),
                pd.concat(tum_kutular, ignore_index=True),
            )
        )

    kosu = kosu_bilgisi(
        veri_kok=arg.veri,
        bolumler=",".join(arg.bolum),
    )
    hedef = csv_yaz(arg.cikti, satirlar, kosu)

    print("\n=== GORUNTU VE ETIKET SAYILARI ===")
    tablo_bas(satirlar, [
        "bolum", "goruntu_sayisi", "gor_genislik_medyan", "gor_yukseklik_medyan",
        "toplam_kutu", "kutu_goruntu_basina",
    ])

    print("\n=== KUTU BOYUTLARI (piksel) ===")
    tablo_bas(satirlar, [
        "bolum",
        "kutu_genislik_min_px", "kutu_genislik_medyan_px", "kutu_genislik_maks_px",
        "kutu_yukseklik_min_px", "kutu_yukseklik_medyan_px", "kutu_yukseklik_maks_px",
        "kutu_alan_orani_medyan_yuzde",
    ])

    # Kaynak bazli dagilim ayri bir tabloya yazilir; kaynaklarin dengesizligi
    # sonraki tum olcumlerin yorumunu belirledigi icin veri tanima adiminin
    # parcasidir.
    onek_satirlari = onek_dagilimi(arg.bolum, arg.veri)
    hedef_onek = csv_yaz(arg.onek_cikti, onek_satirlari, kosu)

    print("\n=== KAYNAK (ONEK) DAGILIMI - tum bolumler birlesik ===")
    tablo_bas([s for s in onek_satirlari if s["bolum"] == "HEPSI"],
              ["onek", "goruntu_sayisi", "kutu_sayisi", "kutu_goruntu_basina", "bos_yuzde"])

    print(f"\nCSV kaydedildi        : {hedef}")
    print(f"Onek dagilimi         : {hedef_onek}  ({len(onek_satirlari)} satir)")


if __name__ == "__main__":
    main()
