"""Kutu bazinda kayittan iki gozlem cikarir. Model taramasi YAPMAZ, model
YUKLEMEZ; tek girdisi 01_taban_cizgisi.py'nin urettigi kutu_bazinda_sonuc.csv'dir.

ANALIZ 1 -- Eslesen kutularin guven skoru dagilimi (conf esigi 0.05'te),
B turu kaynaklar (BLI/GRO/CAB) ile en az 100 kutusu olan diger kaynaklar icin
ayri ayri. Eslesmelerin esigin hemen ustunde mi biriktigini gosterir.

ANALIZ 2 -- Kutu en-boy oraniyla (genislik / yukseklik) recall iliskisi,
conf esigi 0.30'da; ZRI dahil ve ZRI haric olmak uzere iki kapsamda.

Cikti yorumlanmaz, sadece sayilar uretilir.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ortak import (
    RAPOR_KOK,
    csv_yaz,
    kosu_bilgisi,
    sayi_bicimle,
    tablo_bas,
)

# Analiz 1 conf esigi: kutu_bazinda_sonuc.csv'deki en dusuk esik. Eslesen
# skorlarin tam dagilimi ancak bu esikte gorulur; daha yuksek bir esikte
# dusuk bantlar tanim geregi bos kalirdi.
SKOR_CONF = 0.05

# Analiz 1 bantlari: [alt, ust). Son bandin usti dahildir (skor 1.0 olabilir).
BANTLAR = [(0.05, 0.15), (0.15, 0.30), (0.30, 0.50), (0.50, 1.00)]

# "B turu" kaynaklar: 05_kontrast_analiz.py'de boyut modelinden en cok sapan uc kaynak.
B_TURU = ["BLI", "GRO", "CAB"]

# Analiz 2 conf esigi ve en-boy orani sinirlari.
ENBOY_CONF = 0.30
YATAY_ALT = 1.5   # oran > 1.5 -> yatay
DIKEY_UST = 0.8   # oran < 0.8 -> dikey

# Grup buyuklugu bayraklari. Az sayida kutudan cikan oranlar guvenilmez oldugu
# icin bunlar sonucun yaninda tasinir; sayilar hicbir durumda bastirilmaz.
AZ_ORNEK_ESIGI = 100
YETERSIZ_ESIGI = 50

# Analiz 1'de "diger kaynaklar" grubuna girmek icin gereken en az kutu sayisi.
DIGER_EN_AZ_KUTU = 100

YETERSIZ_METIN = "yetersiz ornek"
AZ_ORNEK_METIN = "az ornek"
YETERLI_METIN = "yeterli"


def argumanlari_coz() -> argparse.Namespace:
    """Komut satiri argumanlarini tanimlar ve cozer."""
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Kutu bazinda kayittan eslesme skoru dagilimini ve en-boy orani / recall "
            "iliskisini cikarir. Model calistirmaz. Ciktilar: "
            "reports/eslesme_skor_dagilimi.csv ve reports/enboy_orani_recall.csv"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument(
        "--kutu-sonuc", type=Path, default=RAPOR_KOK / "kutu_bazinda_sonuc.csv",
        help="Kutu bazinda eslesme kaydi (01_taban_cizgisi.py uretir)",
    )
    ayrastirici.add_argument(
        "--skor-cikti", type=Path, default=RAPOR_KOK / "eslesme_skor_dagilimi.csv",
        help="Analiz 1 sonuc CSV yolu",
    )
    ayrastirici.add_argument(
        "--enboy-cikti", type=Path, default=RAPOR_KOK / "enboy_orani_recall.csv",
        help="Analiz 2 sonuc CSV yolu",
    )
    return ayrastirici.parse_args()


def kutu_kaydini_oku(yol: Path) -> pd.DataFrame:
    """Kutu bazinda kaydi okur; dosya yoksa onu ureten komutu gostererek durur."""
    if not yol.is_file():
        raise SystemExit(
            f"Kutu bazinda kayit bulunamadi: {yol}\n"
            "Bu dosyayi 01_taban_cizgisi.py her kosuda uretir. Once su komutu\n"
            "calistirin (tam veri kumesinde ~2.7 saat surer):\n"
            "  .venv/bin/python scripts/01_taban_cizgisi.py --bolum hepsi "
            "--limit 0 --onek-bazinda --cikti reports/taban_cizgisi_onek.csv"
        )
    return pd.read_csv(yol)


def ornek_durumu(kutu_sayisi: int) -> str:
    """Grup buyuklugune gore guvenilirlik bayragini dondurur."""
    if kutu_sayisi < YETERSIZ_ESIGI:
        return YETERSIZ_METIN
    if kutu_sayisi < AZ_ORNEK_ESIGI:
        return AZ_ORNEK_METIN
    return YETERLI_METIN


def bant_adi(alt: float, ust: float) -> str:
    """Bant sinirlarini CSV'de okunacak tek bir etikete cevirir."""
    return f"{alt:.2f}-{ust:.2f}"


def bant_sec(skorlar: pd.Series, alt: float, ust: float) -> pd.Series:
    """Bir bandin icine dusen skorlari secer; son bandin ust siniri dahildir."""
    if ust >= BANTLAR[-1][1]:
        return skorlar[(skorlar >= alt) & (skorlar <= ust)]
    return skorlar[(skorlar >= alt) & (skorlar < ust)]


def skor_dagilimi(df: pd.DataFrame) -> list[dict]:
    """ANALIZ 1: eslesen kutularin skorlarini banda gore sayar.

    Iki grup uretilir: B turu kaynaklar ve en az DIGER_EN_AZ_KUTU kutusu olan
    diger kaynaklar. Grup basina her bant icin bir satir doner. Sayilar her
    durumda yazilir; guvenilirlik iki ayri bayrak sutunuyla bildirilir."""
    esikte = df[df["conf_esigi"] == SKOR_CONF]
    if esikte.empty:
        raise SystemExit(f"Kayitta conf_esigi={SKOR_CONF} satiri yok.")

    # Kaynak basina kutu sayisi: bu esikteki satir sayisi, her gercek kutu icin
    # esik basina tek satir oldugundan dogrudan kutu sayisina esittir.
    kutu_sayilari = esikte["kaynak_onek"].value_counts()
    diger_kaynaklar = sorted(
        onek for onek, adet in kutu_sayilari.items()
        if onek not in B_TURU and adet >= DIGER_EN_AZ_KUTU
    )

    gruplar = [
        ("B_TURU", [k for k in B_TURU if k in kutu_sayilari.index]),
        (f"DIGER_EN_AZ_{DIGER_EN_AZ_KUTU}_KUTU", diger_kaynaklar),
    ]

    satirlar: list[dict] = []
    for grup_adi, kaynaklar in gruplar:
        grup = esikte[esikte["kaynak_onek"].isin(kaynaklar)]
        eslesen = grup[grup["eslesti"] == 1]
        skorlar = pd.to_numeric(eslesen["eslesen_skor"], errors="coerce").dropna()

        # Grup iki farkli buyuklukle olculebilir: gruptaki toplam kutu sayisi ve
        # dagilimin uzerinde hesaplandigi eslesen kutu sayisi. Ikisi ANALIZ 1'de
        # ciddi olcude ayrisir (B turu: 101 kutu ama ~37 eslesme), bu yuzden sayi
        # bastirilmaz; her iki bayrak da satirda ayri ayri tasinir.
        for alt, ust in BANTLAR:
            adet = len(bant_sec(skorlar, alt, ust))
            satirlar.append({
                "grup": grup_adi,
                "kaynaklar": "+".join(kaynaklar) if kaynaklar else "",
                "bant": bant_adi(alt, ust),
                "bant_alt": alt,
                "bant_ust": ust,
                "eslesme_sayisi": adet,
                "bant_yuzde": sayi_bicimle(
                    100 * adet / len(skorlar) if len(skorlar) else 0.0, 1
                ),
                "grup_kutu_sayisi": len(grup),
                "grup_eslesme_sayisi": len(skorlar),
                "ornek_durumu_kutu": ornek_durumu(len(grup)),
                "ornek_durumu_eslesme": ornek_durumu(len(skorlar)),
            })
    return satirlar


def enboy_grubu(oran: float) -> str:
    """En-boy oranini yatay / kare_benzeri / dikey gruplarindan birine atar."""
    if oran > YATAY_ALT:
        return "yatay"
    if oran < DIKEY_UST:
        return "dikey"
    return "kare_benzeri"


def enboy_recall(df: pd.DataFrame) -> list[dict]:
    """ANALIZ 2: en-boy orani grubu basina conf=0.30 recall'i hesaplar.

    Sayilar her durumda yazilir; guvenilirlik ornek_durumu sutunuyla bildirilir.
    Ayni hesap iki kapsamda tekrarlanir: tum kaynaklar ve ZRI haric. ZRI veri
    kumesinin yarisindan fazlasini olusturdugu icin toplu sayiyi tek basina
    belirleyebilir; ayrisip ayrismadigi ancak boyle gorulur."""
    esikte = df[df["conf_esigi"] == ENBOY_CONF].copy()
    if esikte.empty:
        raise SystemExit(f"Kayitta conf_esigi={ENBOY_CONF} satiri yok.")

    # Genislik ve yukseklik kutu bazinda kayitta zaten piksel cinsinden duruyor;
    # etiket dosyalarini yeniden okumaya gerek yok.
    esikte = esikte[esikte["kutu_yukseklik_px"] > 0]
    esikte["enboy_orani"] = esikte["kutu_genislik_px"] / esikte["kutu_yukseklik_px"]
    esikte["enboy_grubu"] = esikte["enboy_orani"].map(enboy_grubu)

    kapsamlar = [
        ("hepsi", esikte),
        ("ZRI_HARIC", esikte[esikte["kaynak_onek"] != "ZRI"]),
    ]
    araliklar = {
        "yatay": f"> {YATAY_ALT:g}",
        "kare_benzeri": f"{DIKEY_UST:g} - {YATAY_ALT:g}",
        "dikey": f"< {DIKEY_UST:g}",
    }

    satirlar: list[dict] = []
    for kapsam_adi, kapsam in kapsamlar:
        for grup_adi in ("yatay", "kare_benzeri", "dikey"):
            grup = kapsam[kapsam["enboy_grubu"] == grup_adi]
            tp = int((grup["eslesti"] == 1).sum())
            satirlar.append({
                "kapsam": kapsam_adi,
                "grup": grup_adi,
                "oran_araligi": araliklar[grup_adi],
                "kutu_sayisi": len(grup),
                "dogru_bulunan_tp": tp,
                "kacirilan_fn": len(grup) - tp,
                "recall": sayi_bicimle(tp / len(grup) if len(grup) else 0.0),
                "medyan_enboy_orani": sayi_bicimle(
                    float(grup["enboy_orani"].median()), 3
                ) if len(grup) else "",
                "ornek_durumu": ornek_durumu(len(grup)),
            })
    return satirlar


def main() -> None:
    """Iki analizi calistirir, CSV'leri yazar ve tablolari ekrana basar."""
    arg = argumanlari_coz()
    df = kutu_kaydini_oku(arg.kutu_sonuc)

    print(f"Girdi: {arg.kutu_sonuc}  ({len(df)} satir) | Model taramasi YOK\n")

    skor_satirlari = skor_dagilimi(df)
    enboy_satirlari = enboy_recall(df)

    ortak_kosu = dict(
        girdi_dosyasi=arg.kutu_sonuc.name,
        girdi_satir_sayisi=len(df),
        az_ornek_esigi=AZ_ORNEK_ESIGI,
        yetersiz_ornek_esigi=YETERSIZ_ESIGI,
        not_="model taramasi yapilmadi; tum sayilar kutu bazinda kayittan turetildi",
    )

    skor_kosu = kosu_bilgisi(
        analiz="eslesme skoru dagilimi",
        conf_esigi=SKOR_CONF,
        bantlar=" / ".join(bant_adi(a, u) for a, u in BANTLAR),
        b_turu_kaynaklar="+".join(B_TURU),
        diger_grup_en_az_kutu=DIGER_EN_AZ_KUTU,
        **ortak_kosu,
    )
    enboy_kosu = kosu_bilgisi(
        analiz="en-boy orani / recall",
        conf_esigi=ENBOY_CONF,
        enboy_tanimi="genislik_px / yukseklik_px",
        grup_sinirlari=f"yatay > {YATAY_ALT:g}; kare_benzeri {DIKEY_UST:g}-{YATAY_ALT:g}; dikey < {DIKEY_UST:g}",
        **ortak_kosu,
    )

    skor_hedef = csv_yaz(arg.skor_cikti, skor_satirlari, skor_kosu)
    enboy_hedef = csv_yaz(arg.enboy_cikti, enboy_satirlari, enboy_kosu)

    print(f"=== ANALIZ 1: ESLESEN KUTULARIN SKOR DAGILIMI (conf={SKOR_CONF}) ===")
    tablo_bas(skor_satirlari, ["grup", "bant", "eslesme_sayisi", "bant_yuzde",
                               "grup_kutu_sayisi", "grup_eslesme_sayisi",
                               "ornek_durumu_kutu", "ornek_durumu_eslesme"])

    print(f"\n=== ANALIZ 2: EN-BOY ORANI ve RECALL (conf={ENBOY_CONF}) ===")
    tablo_bas(enboy_satirlari, ["kapsam", "grup", "oran_araligi", "kutu_sayisi",
                                "dogru_bulunan_tp", "recall", "medyan_enboy_orani",
                                "ornek_durumu"])

    print(f"\nCSV kaydedildi: {skor_hedef}")
    print(f"CSV kaydedildi: {enboy_hedef}")


if __name__ == "__main__":
    main()
