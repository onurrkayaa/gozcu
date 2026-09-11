"""Kutu bazinda kayittan iki kontrol analizi cikarir. Model taramasi YAPMAZ, model
YUKLEMEZ; tek girdisi 01_taban_cizgisi.py'nin urettigi kutu_bazinda_sonuc.csv'dir.

ANALIZ 3 -- En-boy orani etkisinin boyuttan bagimsiz olup olmadigini tabakali
olarak sinar: kutular alanlarina gore uc tabakaya bolunur ve recall her tabakanin
ICINDE oran gruplarina gore ayri ayri hesaplanir. Boylece oran ile boyut birbirine
karismaz.

ANALIZ 4 -- Genislik, yukseklik ve alan olculerinin recall'i ne kadar iyi
ongordugunu karsilastirir: her olcu kendi verisinden hesaplanan bes esit gruba
bolunur ve grup basina recall yazilir; ayrica her olcunun 'eslesti' ikili
degiskeniyle nokta-cift korelasyonu verilir.

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

# Analiz 3: en-boy orani gruplari (07_gozlem_analiz.py ile ayni sinirlar).
YATAY_ALT = 1.5   # oran > 1.5 -> yatay
DIKEY_UST = 0.8   # oran < 0.8 -> dikey
ORAN_GRUPLARI = ("yatay", "kare_benzeri", "dikey")

# Analiz 3: alan tabakasi sayisi (uclu ceyrek) ve tabaka adlari.
TABAKA_SAYISI = 3
TABAKA_ADLARI = ("kucuk", "orta", "buyuk")

# Analiz 4: olcu basina esit sayida kutu iceren grup sayisi.
QUINTILE_SAYISI = 5
OLCULER = ("kutu_genislik_px", "kutu_yukseklik_px", "kutu_alan_px2")

# Grup buyuklugu bayraklari. Sayilar her durumda yazilir; bayrak yalnizca
# grubun ne kadar kucuk oldugunu bildirir.
AZ_ORNEK_ESIGI = 100
YETERSIZ_ESIGI = 50


def argumanlari_coz() -> argparse.Namespace:
    """Komut satiri argumanlarini tanimlar ve cozer."""
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Kutu bazinda kayittan (1) oran etkisinin alan tabakasi icinde korunup "
            "korunmadigini ve (2) genislik/yukseklik/alan olculerinin recall'i ne kadar "
            "ongordugunu cikarir. Model calistirmaz. Ciktilar: "
            "reports/oran_boyut_tabakali.csv ve reports/olcu_karsilastirma.csv"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument(
        "--kutu-sonuc", type=Path, default=RAPOR_KOK / "kutu_bazinda_sonuc.csv",
        help="Kutu bazinda eslesme kaydi (01_taban_cizgisi.py uretir)",
    )
    ayrastirici.add_argument(
        "--tabakali-cikti", type=Path, default=RAPOR_KOK / "oran_boyut_tabakali.csv",
        help="Analiz 3 sonuc CSV yolu",
    )
    ayrastirici.add_argument(
        "--olcu-cikti", type=Path, default=RAPOR_KOK / "olcu_karsilastirma.csv",
        help="Analiz 4 sonuc CSV yolu",
    )
    return ayrastirici.parse_args()


def kutu_kaydini_oku(yol: Path) -> pd.DataFrame:
    """Kutu bazinda kaydi conf esiginde filtreleyerek okur; her gercek kutu icin
    tek satir kalir. Dosya yoksa onu ureten komutu gostererek durur."""
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

    # Alan, kutu boyutlarindan yeniden hesaplanir; kayittaki hazir sutun yerine
    # acik formul kullanmak tabaka sinirlarinin neyden turedigini belirsiz birakmaz.
    df["alan_px2"] = df["kutu_genislik_px"] * df["kutu_yukseklik_px"]
    df = df[df["kutu_yukseklik_px"] > 0]
    df["enboy_orani"] = df["kutu_genislik_px"] / df["kutu_yukseklik_px"]
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
    """ANALIZ 3: her alan tabakasinin icinde oran grubu basina recall hesaplar.

    Tabaka sinirlari her kapsam icin o kapsamin KENDI alan dagilimindan yeniden
    hesaplanir; ZRI cikarildiginda dagilim degistigi icin eski sinirlar tabakalari
    dengesiz birakirdi. Kullanilan sinirlar her satira yazilir."""
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
            float(kapsam["alan_px2"].quantile(i / TABAKA_SAYISI))
            for i in range(1, TABAKA_SAYISI)
        ]
        sinirlar[kapsam_adi] = kesim
        kenarlar = [-np.inf, *kesim, np.inf]
        kapsam = kapsam.assign(
            tabaka=pd.cut(kapsam["alan_px2"], bins=kenarlar, labels=list(TABAKA_ADLARI))
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
                    "alan_tabakasi": tabaka_adi,
                    "tabaka_alt_px2": "" if np.isinf(alt) else sayi_bicimle(alt, 1),
                    "tabaka_ust_px2": "" if np.isinf(ust) else sayi_bicimle(ust, 1),
                    "oran_grubu": grup_adi,
                    "oran_araligi": araliklar[grup_adi],
                    "kutu_sayisi": len(grup),
                    "dogru_bulunan_tp": tp,
                    "kacirilan_fn": len(grup) - tp,
                    "recall": sayi_bicimle(tp / len(grup) if len(grup) else 0.0),
                    "medyan_alan_px2": sayi_bicimle(grup["alan_px2"].median(), 1) if len(grup) else "",
                    "medyan_genislik_px": sayi_bicimle(grup["kutu_genislik_px"].median(), 1) if len(grup) else "",
                    "medyan_yukseklik_px": sayi_bicimle(grup["kutu_yukseklik_px"].median(), 1) if len(grup) else "",
                    "medyan_enboy_orani": sayi_bicimle(grup["enboy_orani"].median(), 3) if len(grup) else "",
                    "ornek_durumu": ornek_durumu(len(grup)),
                })
    return satirlar, sinirlar


def nokta_cift_korelasyon(olcu: pd.Series, ikili: pd.Series) -> float:
    """Surekli bir olcu ile ikili bir degisken arasindaki nokta-cift korelasyonu.
    Bu, ikili degisken 0/1 olarak kodlandiginda Pearson katsayisina esittir."""
    return float(np.corrcoef(olcu.to_numpy(float), ikili.to_numpy(float))[0, 1])


def olcu_satirlari(df: pd.DataFrame) -> tuple[list[dict], dict[str, list[float]]]:
    """ANALIZ 4: uc olcunun her birini esit sayida kutu iceren bes gruba bolup
    grup basina recall yazar ve olcunun 'eslesti' ile korelasyonunu ekler."""
    satirlar: list[dict] = []
    sinirlar: dict[str, list[float]] = {}

    for olcu in OLCULER:
        kesim = [
            float(df[olcu].quantile(i / QUINTILE_SAYISI))
            for i in range(1, QUINTILE_SAYISI)
        ]
        sinirlar[olcu] = kesim
        kenarlar = [-np.inf, *kesim, np.inf]
        # Ayni degerin iki sinira denk gelmesi gruplari birlestirebilir; bu durumda
        # grup sayisi besin altina duser ve asagidaki dongu bos gruplari atlar.
        etiketler = list(range(1, QUINTILE_SAYISI + 1))
        gruplar = pd.cut(df[olcu], bins=kenarlar, labels=etiketler, duplicates="drop")

        korelasyon = nokta_cift_korelasyon(df[olcu], df["eslesti"])

        for sira, etiket in enumerate(etiketler):
            grup = df[gruplar == etiket]
            if grup.empty:
                continue
            alt = kenarlar[sira]
            ust = kenarlar[sira + 1]
            tp = int((grup["eslesti"] == 1).sum())
            satirlar.append({
                "olcu": olcu,
                "grup_no": etiket,
                "grup_alt": "" if np.isinf(alt) else sayi_bicimle(alt, 1),
                "grup_ust": "" if np.isinf(ust) else sayi_bicimle(ust, 1),
                "kutu_sayisi": len(grup),
                "dogru_bulunan_tp": tp,
                "kacirilan_fn": len(grup) - tp,
                "recall": sayi_bicimle(tp / len(grup)),
                "medyan_olcu": sayi_bicimle(grup[olcu].median(), 1),
                "nokta_cift_korelasyon": sayi_bicimle(korelasyon),
                "ornek_durumu": ornek_durumu(len(grup)),
            })
    return satirlar, sinirlar


def sinir_metni(sinirlar: dict[str, list[float]]) -> str:
    """Hesaplanan grup sinirlarini kosu bilgisine yazilacak tek satira cevirir."""
    return "; ".join(
        f"{ad}: {', '.join(f'{d:.1f}' for d in degerler)}"
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
        analiz="oran etkisi / alan tabakasi kontrolu",
        alan_tanimi="genislik_px * yukseklik_px",
        tabaka_sayisi=TABAKA_SAYISI,
        tabaka_yontemi="kapsamin kendi alan dagiliminin uclu ceyrekleri",
        tabaka_sinirlari_px2=sinir_metni(tabaka_sinir),
        oran_sinirlari=f"yatay > {YATAY_ALT:g}; kare_benzeri {DIKEY_UST:g}-{YATAY_ALT:g}; dikey < {DIKEY_UST:g}",
        **ortak_kosu,
    )
    olcu_kosu = kosu_bilgisi(
        analiz="olcu karsilastirmasi (genislik / yukseklik / alan)",
        grup_sayisi=QUINTILE_SAYISI,
        grup_yontemi="her olcunun kendi dagiliminin besli ceyrekleri",
        grup_sinirlari=sinir_metni(olcu_sinir),
        korelasyon_tanimi="nokta-cift (olcu ile ikili eslesti degiskeni arasinda Pearson)",
        **ortak_kosu,
    )

    tabaka_hedef = csv_yaz(arg.tabakali_cikti, tabaka_satir, tabaka_kosu)
    olcu_hedef = csv_yaz(arg.olcu_cikti, olcu_satir, olcu_kosu)

    print("=== TABAKA SINIRLARI (alan, px2) ===")
    for ad, degerler in tabaka_sinir.items():
        print(f"  {ad:10s}: {' | '.join(f'{d:.1f}' for d in degerler)}")

    print(f"\n=== ANALIZ 3: ALAN TABAKASI ICINDE ORAN ve RECALL (conf={CONF}) ===")
    tablo_bas(tabaka_satir, ["kapsam", "alan_tabakasi", "oran_grubu", "kutu_sayisi",
                             "dogru_bulunan_tp", "recall", "medyan_alan_px2",
                             "medyan_genislik_px", "medyan_yukseklik_px", "ornek_durumu"])

    print("\n=== QUINTILE SINIRLARI ===")
    for ad, degerler in olcu_sinir.items():
        print(f"  {ad:18s}: {' | '.join(f'{d:.1f}' for d in degerler)}")

    print(f"\n=== ANALIZ 4: OLCU BASINA RECALL EGRISI (conf={CONF}) ===")
    tablo_bas(olcu_satir, ["olcu", "grup_no", "grup_alt", "grup_ust", "kutu_sayisi",
                           "dogru_bulunan_tp", "recall", "medyan_olcu",
                           "nokta_cift_korelasyon", "ornek_durumu"])

    print(f"\nCSV kaydedildi: {tabaka_hedef}")
    print(f"CSV kaydedildi: {olcu_hedef}")


if __name__ == "__main__":
    main()
