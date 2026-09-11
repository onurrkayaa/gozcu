"""Kutu bazinda kayittan iki kontrol analizi daha cikarir. Model taramasi YAPMAZ,
model YUKLEMEZ; tek girdisi 01_taban_cizgisi.py'nin urettigi kutu_bazinda_sonuc.csv'dir.

ANALIZ 5 -- En-boy orani etkisinin yukseklikten bagimsiz olup olmadigini sinar.
08_oran_boyut_kontrol.py alani sabitliyordu; burada tabakalar dogrudan kutu
yuksekligine gore kuruluyor, cunku oran ile yukseklik birbirine gomulu iki olcu.

ANALIZ 6 -- Recall'i en iyi hangi olcunun ongordugunu genisletilmis bir listeyle
karsilastirir: min kenar, maks kenar ve yukseklik/genislik oraninin kendisi; ayrica
genislik, yukseklik ve alan da karsilastirma icin ayni tabloda tekrar hesaplanir.

Cikti yorumlanmaz, sadece sayilar uretilir.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ortak import RAPOR_KOK, csv_yaz, kosu_bilgisi, sayi_bicimle, tablo_bas

# Her iki analiz de tek bir guven esiginde calisir.
CONF = 0.30

# Analiz 5: en-boy orani gruplari (07 ve 08 ile ayni sinirlar).
YATAY_ALT = 1.5   # oran > 1.5 -> yatay
DIKEY_UST = 0.8   # oran < 0.8 -> dikey
ORAN_GRUPLARI = ("yatay", "kare_benzeri", "dikey")

# Analiz 5: yukseklik tabakasi sayisi ve tabaka adlari.
TABAKA_SAYISI = 3
TABAKA_ADLARI = ("kisa", "orta", "uzun")

# Analiz 6: olcu basina esit sayida kutu iceren grup sayisi.
QUINTILE_SAYISI = 5

# Analiz 6'da karsilastirilan olculer. Ilk uc tanesi bu analizin asil konusu;
# son uc tanesi 08'de de olcuduklerimiz, ayni tabloda karsilastirilabilsin diye
# burada tekrar hesaplaniyor.
OLCULER = (
    "min_kenar_px",
    "maks_kenar_px",
    "yukseklik_genislik_orani",
    "kutu_genislik_px",
    "kutu_yukseklik_px",
    "alan_px2",
)

# Grup buyuklugu bayraklari. Sayilar her durumda yazilir; bayrak yalnizca
# grubun ne kadar kucuk oldugunu bildirir.
AZ_ORNEK_ESIGI = 100
YETERSIZ_ESIGI = 50


def argumanlari_coz() -> argparse.Namespace:
    """Komut satiri argumanlarini tanimlar ve cozer."""
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Kutu bazinda kayittan (1) oran etkisinin yukseklik tabakasi icinde korunup "
            "korunmadigini ve (2) genisletilmis bir olcu listesinin recall'i ne kadar "
            "ongordugunu cikarir. Model calistirmaz. Ciktilar: "
            "reports/oran_yukseklik_tabakali.csv ve reports/olcu_karsilastirma_genis.csv"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument(
        "--kutu-sonuc", type=Path, default=RAPOR_KOK / "kutu_bazinda_sonuc.csv",
        help="Kutu bazinda eslesme kaydi (01_taban_cizgisi.py uretir)",
    )
    ayrastirici.add_argument(
        "--tabakali-cikti", type=Path, default=RAPOR_KOK / "oran_yukseklik_tabakali.csv",
        help="Analiz 5 sonuc CSV yolu",
    )
    ayrastirici.add_argument(
        "--olcu-cikti", type=Path, default=RAPOR_KOK / "olcu_karsilastirma_genis.csv",
        help="Analiz 6 sonuc CSV yolu",
    )
    return ayrastirici.parse_args()


def kutu_kaydini_oku(yol: Path) -> pd.DataFrame:
    """Kutu bazinda kaydi conf esiginde filtreleyip turetilmis olculeri ekler."""
    if not yol.is_file():
        raise SystemExit(
            f"Kutu bazinda kayit bulunamadi: {yol}\n"
            "Bu dosyayi 01_taban_cizgisi.py her kosuda uretir. Once su komutu\n"
            "calistirin (tam veri kumesinde ~2.6 saat surer):\n"
            "  .venv/bin/python scripts/01_taban_cizgisi.py --bolum hepsi "
            "--limit 0 --onek-bazinda --cikti reports/taban_cizgisi_onek.csv"
        )
    df = pd.read_csv(yol)
    df = df[df["conf_esigi"] == CONF].copy()
    if df.empty:
        raise SystemExit(f"Kayitta conf_esigi={CONF} satiri yok.")

    df = df[(df["kutu_yukseklik_px"] > 0) & (df["kutu_genislik_px"] > 0)]
    genislik = df["kutu_genislik_px"]
    yukseklik = df["kutu_yukseklik_px"]
    df["alan_px2"] = genislik * yukseklik
    df["enboy_orani"] = genislik / yukseklik
    # Oran grubu genislik/yukseklik ile tanimli; olcu olarak ise bunun tersi
    # (yukseklik/genislik) isteniyor, ikisi ayri sutunlarda tutuluyor.
    df["yukseklik_genislik_orani"] = yukseklik / genislik
    df["min_kenar_px"] = np.minimum(genislik, yukseklik)
    df["maks_kenar_px"] = np.maximum(genislik, yukseklik)
    return df


def ornek_durumu(kutu_sayisi: int) -> str:
    """Grup buyuklugune gore guvenilirlik bayragini dondurur."""
    if kutu_sayisi < YETERSIZ_ESIGI:
        return "yetersiz ornek"
    if kutu_sayisi < AZ_ORNEK_ESIGI:
        return "az ornek"
    return "yeterli"


def oran_grubu(oran: float) -> str:
    """En-boy oranini yatay / kare_benzeri / dikey gruplarindan birine atar."""
    if oran > YATAY_ALT:
        return "yatay"
    if oran < DIKEY_UST:
        return "dikey"
    return "kare_benzeri"


def tabakali_satirlar(df: pd.DataFrame) -> tuple[list[dict], dict[str, list[float]]]:
    """ANALIZ 5: her yukseklik tabakasinin icinde oran grubu basina recall hesaplar.

    Tabaka sinirlari her kapsam icin o kapsamin KENDI yukseklik dagilimindan
    yeniden hesaplanir ve her satira yazilir."""
    araliklar = {
        "yatay": f"> {YATAY_ALT:g}",
        "kare_benzeri": f"{DIKEY_UST:g} - {YATAY_ALT:g}",
        "dikey": f"< {DIKEY_UST:g}",
    }
    kapsamlar = [("hepsi", df), ("ZRI_HARIC", df[df["kaynak_onek"] != "ZRI"])]

    satirlar: list[dict] = []
    sinirlar: dict[str, list[float]] = {}

    for kapsam_adi, kapsam in kapsamlar:
        kesim = [
            float(kapsam["kutu_yukseklik_px"].quantile(i / TABAKA_SAYISI))
            for i in range(1, TABAKA_SAYISI)
        ]
        sinirlar[kapsam_adi] = kesim
        kenarlar = [-np.inf, *kesim, np.inf]
        kapsam = kapsam.assign(
            tabaka=pd.cut(
                kapsam["kutu_yukseklik_px"], bins=kenarlar, labels=list(TABAKA_ADLARI)
            )
        )

        for sira, tabaka_adi in enumerate(TABAKA_ADLARI):
            tabaka = kapsam[kapsam["tabaka"] == tabaka_adi]
            alt = kenarlar[sira]
            ust = kenarlar[sira + 1]
            for grup_adi in ORAN_GRUPLARI:
                grup = tabaka[tabaka["enboy_orani"].map(oran_grubu) == grup_adi]
                tp = int((grup["eslesti"] == 1).sum())
                satirlar.append({
                    "kapsam": kapsam_adi,
                    "yukseklik_tabakasi": tabaka_adi,
                    "tabaka_alt_px": "" if np.isinf(alt) else sayi_bicimle(alt, 1),
                    "tabaka_ust_px": "" if np.isinf(ust) else sayi_bicimle(ust, 1),
                    "oran_grubu": grup_adi,
                    "oran_araligi": araliklar[grup_adi],
                    "kutu_sayisi": len(grup),
                    "dogru_bulunan_tp": tp,
                    "kacirilan_fn": len(grup) - tp,
                    "recall": sayi_bicimle(tp / len(grup) if len(grup) else 0.0),
                    "medyan_yukseklik_px": sayi_bicimle(grup["kutu_yukseklik_px"].median(), 1) if len(grup) else "",
                    "medyan_genislik_px": sayi_bicimle(grup["kutu_genislik_px"].median(), 1) if len(grup) else "",
                    "medyan_alan_px2": sayi_bicimle(grup["alan_px2"].median(), 1) if len(grup) else "",
                    "medyan_enboy_orani": sayi_bicimle(grup["enboy_orani"].median(), 3) if len(grup) else "",
                    "ornek_durumu": ornek_durumu(len(grup)),
                })
    return satirlar, sinirlar


def nokta_cift_korelasyon(olcu: pd.Series, ikili: pd.Series) -> float:
    """Surekli bir olcu ile ikili bir degisken arasindaki nokta-cift korelasyonu.
    Bu, ikili degisken 0/1 olarak kodlandiginda Pearson katsayisina esittir."""
    return float(np.corrcoef(olcu.to_numpy(float), ikili.to_numpy(float))[0, 1])


def olcu_satirlari(df: pd.DataFrame) -> tuple[list[dict], dict[str, list[float]]]:
    """ANALIZ 6: her olcuyu esit sayida kutu iceren bes gruba bolup grup basina
    recall yazar ve olcunun 'eslesti' ile korelasyonunu ekler."""
    satirlar: list[dict] = []
    sinirlar: dict[str, list[float]] = {}

    for olcu in OLCULER:
        kesim = [
            float(df[olcu].quantile(i / QUINTILE_SAYISI))
            for i in range(1, QUINTILE_SAYISI)
        ]
        sinirlar[olcu] = kesim
        kenarlar = [-np.inf, *kesim, np.inf]
        etiketler = list(range(1, QUINTILE_SAYISI + 1))
        # Ayni deger iki sinira denk gelirse grup sayisi besin altina duser;
        # asagidaki dongu olusmayan gruplari atlar.
        gruplar = pd.cut(df[olcu], bins=kenarlar, labels=etiketler, duplicates="drop")

        korelasyon = nokta_cift_korelasyon(df[olcu], df["eslesti"])

        for sira, etiket in enumerate(etiketler):
            grup = df[gruplar == etiket]
            if grup.empty:
                continue
            alt = kenarlar[sira]
            ust = kenarlar[sira + 1]
            tp = int((grup["eslesti"] == 1).sum())
            basamak = 3 if "orani" in olcu else 1
            satirlar.append({
                "olcu": olcu,
                "grup_no": etiket,
                "grup_alt": "" if np.isinf(alt) else sayi_bicimle(alt, basamak),
                "grup_ust": "" if np.isinf(ust) else sayi_bicimle(ust, basamak),
                "kutu_sayisi": len(grup),
                "dogru_bulunan_tp": tp,
                "kacirilan_fn": len(grup) - tp,
                "recall": sayi_bicimle(tp / len(grup)),
                "medyan_olcu": sayi_bicimle(grup[olcu].median(), basamak),
                "nokta_cift_korelasyon": sayi_bicimle(korelasyon),
                "ornek_durumu": ornek_durumu(len(grup)),
            })
    return satirlar, sinirlar


def sinir_metni(sinirlar: dict[str, list[float]]) -> str:
    """Hesaplanan grup sinirlarini kosu bilgisine yazilacak tek satira cevirir."""
    return "; ".join(
        f"{ad}: {', '.join(f'{d:.3f}' if 'orani' in ad else f'{d:.1f}' for d in degerler)}"
        for ad, degerler in sinirlar.items()
    )


def main() -> None:
    """Iki analizi calistirir, CSV'leri yazar ve tablolari ekrana basar."""
    arg = argumanlari_coz()
    df = kutu_kaydini_oku(arg.kutu_sonuc)

    print(f"Girdi: {arg.kutu_sonuc} | conf={CONF} | {len(df)} kutu | Model taramasi YOK\n")

    tabaka_satir, tabaka_sinir = tabakali_satirlar(df)
    olcu_satir, olcu_sinir = olcu_satirlari(df)

    ortak_kosu = dict(
        conf_esigi=CONF,
        girdi_dosyasi=arg.kutu_sonuc.name,
        kutu_sayisi=len(df),
        az_ornek_esigi=AZ_ORNEK_ESIGI,
        yetersiz_ornek_esigi=YETERSIZ_ESIGI,
        not_="model taramasi yapilmadi; tum sayilar kutu bazinda kayittan turetildi",
    )

    tabaka_kosu = kosu_bilgisi(
        analiz="oran etkisi / yukseklik tabakasi kontrolu",
        tabaka_olcusu="kutu_yukseklik_px",
        tabaka_sayisi=TABAKA_SAYISI,
        tabaka_yontemi="kapsamin kendi yukseklik dagiliminin uclu ceyrekleri",
        tabaka_sinirlari_px=sinir_metni(tabaka_sinir),
        oran_sinirlari=f"yatay > {YATAY_ALT:g}; kare_benzeri {DIKEY_UST:g}-{YATAY_ALT:g}; dikey < {DIKEY_UST:g}",
        **ortak_kosu,
    )
    olcu_kosu = kosu_bilgisi(
        analiz="genisletilmis olcu karsilastirmasi",
        olculer=", ".join(OLCULER),
        grup_sayisi=QUINTILE_SAYISI,
        grup_yontemi="her olcunun kendi dagiliminin besli ceyrekleri",
        grup_sinirlari=sinir_metni(olcu_sinir),
        korelasyon_tanimi="nokta-cift (olcu ile ikili eslesti degiskeni arasinda Pearson)",
        **ortak_kosu,
    )

    tabaka_hedef = csv_yaz(arg.tabakali_cikti, tabaka_satir, tabaka_kosu)
    olcu_hedef = csv_yaz(arg.olcu_cikti, olcu_satir, olcu_kosu)

    print("=== TABAKA SINIRLARI (yukseklik, px) ===")
    for ad, degerler in tabaka_sinir.items():
        print(f"  {ad:10s}: {' | '.join(f'{d:.1f}' for d in degerler)}")

    print(f"\n=== ANALIZ 5: YUKSEKLIK TABAKASI ICINDE ORAN ve RECALL (conf={CONF}) ===")
    tablo_bas(tabaka_satir, ["kapsam", "yukseklik_tabakasi", "oran_grubu", "kutu_sayisi",
                             "dogru_bulunan_tp", "recall", "medyan_yukseklik_px",
                             "medyan_genislik_px", "ornek_durumu"])

    print("\n=== QUINTILE SINIRLARI ===")
    for ad, degerler in olcu_sinir.items():
        basamak = 3 if "orani" in ad else 1
        print(f"  {ad:24s}: {' | '.join(f'{d:.{basamak}f}' for d in degerler)}")

    print(f"\n=== ANALIZ 6: GENISLETILMIS OLCU KARSILASTIRMASI (conf={CONF}) ===")
    tablo_bas(olcu_satir, ["olcu", "grup_no", "grup_alt", "grup_ust", "kutu_sayisi",
                           "dogru_bulunan_tp", "recall", "medyan_olcu",
                           "nokta_cift_korelasyon", "ornek_durumu"])

    print(f"\nCSV kaydedildi: {tabaka_hedef}")
    print(f"CSV kaydedildi: {olcu_hedef}")


if __name__ == "__main__":
    main()
