"""Kutu bazinda kayitlardan taban ve egitilmis modeli karsilastirir.

YENI TARAMA YAPMAZ. Girdisi yalnizca daha onceki kosularin kutu bazinda
CSV'leridir; bu yuzden saniyeler icinde calisir.

Turetilebilen ve turetilemeyen sey:
- recall(conf) TURETILEBILIR. Kayittaki eslesen_skor, o hedefi bulan tahminin
  guven skorudur; hedef, skoru esikten buyuk oldugu surece eslesmis sayilir.
  Bu turetim olculmus uc esikte (0,05 / 0,15 / 0,30) birebir dogrulanmistir.
- FP/goruntu TURETILEMEZ. Kutu bazinda kayit yalnizca GERCEK kutulari icerir;
  hicbir hedefle eslesmeyen tahminler (FP'ler) hicbir dosyaya yazilmamistir.
  Bu yuzden FP sutunu yalnizca olculmus uc esikte doludur, digerlerinde
  "olculmedi" yazar.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ortak import RAPOR_KOK, csv_yaz, kosu_bilgisi, sayi_bicimle  # noqa: E402

# Hafta 0'da olculen kutu yuksekligi bestebirlik sinirlari.
YUKSEKLIK_SINIRLARI = [44.0, 55.0, 65.0, 80.0]

# Bir grubun sayilarinin tek basina yorumlanmamasi gereken alt sinir.
AZ_ORNEK_SINIRI = 50

# kosu adi -> (kutu bazinda kayit, ozet CSV, tahmin kaydi | None)
# Tahmin kaydi olmayan kosuda FP egrisi turetilemez; o kosunun FP sutunu
# yalnizca ozet CSV'de olculmus esiklerde dolar.
KOSULAR = {
    "Taban-512": ("reports/test_kutu_bazinda.csv", "reports/test_taban_cizgisi.csv", None),
    "Model-512": ("reports/test_kutu_bazinda_model512.csv", "reports/test_model512.csv",
                  "reports/tahminler_model512.csv"),
}

# Test bolumunde ZRI disinda yalnizca VRD var; ZRI_HARIC satiri bu yuzden
# 31 hedefe dayanir ve tek basina yorumlanamaz.
GRUPLAR = ("TOPLAM", "ZRI", "ZRI_HARIC")


def gruba_girer(satir: dict, grup: str) -> bool:
    if grup == "TOPLAM":
        return True
    if grup == "ZRI":
        return satir["kaynak_onek"] == "ZRI"
    return satir["kaynak_onek"] != "ZRI"


def taban_satirlari(kutu_csv: Path) -> list[dict]:
    """En dusuk esikteki satirlar: her hedef burada bir kez gecer."""
    satirlar = list(csv.DictReader(kutu_csv.open(encoding="utf-8")))
    en_dusuk = min(satirlar, key=lambda s: float(s["conf_esigi"]))["conf_esigi"]
    return [s for s in satirlar if s["conf_esigi"] == en_dusuk]


def olculen_fp(ozet_csv: Path) -> dict[tuple[str, float], float]:
    """Ozet CSV'den (grup, conf) -> FP/goruntu haritasi. Sadece olculmus esikler."""
    harita = {}
    for s in csv.DictReader(ozet_csv.open(encoding="utf-8")):
        harita[(s["kaynak_onek"], float(s["conf_esigi"]))] = float(s["fp_goruntu_basina"])
    return harita


def goruntu_sayilari(ozet_csv: Path) -> dict[str, int]:
    """Grup basina goruntu sayisini OZET CSV'den alir.

    Kutu bazinda kayittan saymak yanlis olurdu: o dosya yalnizca hedefi OLAN
    goruntuleri icerir (157 yerine 112). FP/goruntu bu sayiya bolundugu icin
    fark onemlidir."""
    harita: dict[str, int] = {}
    for s in csv.DictReader(ozet_csv.open(encoding="utf-8")):
        harita[s["kaynak_onek"]] = int(s["goruntu_sayisi"])
    return {g: harita[g] for g in GRUPLAR}


def tahmin_fp_sayaci(tahmin_csv: Path) -> dict[str, list[float]]:
    """Grup basina FP tahminlerin skor listesini dondurur.

    Eslestirme skora gore azalan sirada gezdigi icin, esik yukseltmek yalnizca
    en dusuk skorlu tahminleri atar ve ustte kalanlarin TP/FP etiketi degismez.
    Bu yuzden bir esikteki FP sayisi = skoru o esikten buyuk olan FP satirlari."""
    skorlar: dict[str, list[float]] = {g: [] for g in GRUPLAR}
    for s in csv.DictReader(tahmin_csv.open(encoding="utf-8")):
        if s["eslesme_durumu"] != "FP":
            continue
        for g in GRUPLAR:
            if gruba_girer(s, g):
                skorlar[g].append(float(s["skor"]))
    return skorlar


def esik_taramasi(adim: float, alt: float, ust: float) -> list[dict]:
    """Her kosu, her grup ve her esik icin recall; FP yalnizca olculmus esiklerde."""
    cikti: list[dict] = []
    for kosu_adi, (kutu_yolu, ozet_yolu, tahmin_yolu) in KOSULAR.items():
        satirlar = taban_satirlari(Path(kutu_yolu))
        fp_haritasi = olculen_fp(Path(ozet_yolu))
        goruntu = goruntu_sayilari(Path(ozet_yolu))
        fp_skorlari = tahmin_fp_sayaci(Path(tahmin_yolu)) if tahmin_yolu else None

        for grup in GRUPLAR:
            grup_satir = [s for s in satirlar if gruba_girer(s, grup)]
            skorlar = [float(s["eslesen_skor"]) for s in grup_satir if s["eslesen_skor"]]
            hedef = len(grup_satir)

            esik = alt
            while esik <= ust + 1e-9:
                tp = sum(1 for sk in skorlar if sk >= esik - 1e-9)

                if fp_skorlari is not None:
                    fp_sayi = sum(1 for sk in fp_skorlari[grup] if sk >= esik - 1e-9)
                    fp = fp_sayi / goruntu[grup]
                    kaynak = "tahmin kaydindan turetildi"
                else:
                    fp = fp_haritasi.get((grup, round(esik, 2)))
                    kaynak = "ozet CSV'de olculdu" if fp is not None else "olculmedi"
                cikti.append({
                    "kosu": kosu_adi,
                    "grup": grup,
                    "conf_esigi": round(esik, 2),
                    "goruntu_sayisi": goruntu[grup],
                    "hedef_sayisi": hedef,
                    "dogru_bulunan_tp": tp,
                    "kacirilan_fn": hedef - tp,
                    "recall": sayi_bicimle(tp / hedef if hedef else 0.0),
                    "fp_goruntu_basina": sayi_bicimle(fp, 2) if fp is not None else "olculmedi",
                    "fp_durumu": kaynak,
                    "az_ornek": "az ornek" if hedef < AZ_ORNEK_SINIRI else "",
                })
                esik += adim
    return cikti


def yukseklik_bandi(yukseklik: float) -> tuple[int, str]:
    """Kutu yuksekligini Hafta 0 bestebirlik bantlarindan birine yerlestirir."""
    sinir = YUKSEKLIK_SINIRLARI
    etiketler = [
        f"<{sinir[0]:.0f}",
        f"{sinir[0]:.0f}-{sinir[1]:.0f}",
        f"{sinir[1]:.0f}-{sinir[2]:.0f}",
        f"{sinir[2]:.0f}-{sinir[3]:.0f}",
        f">={sinir[3]:.0f}",
    ]
    for i, s in enumerate(sinir):
        if yukseklik < s:
            return i, etiketler[i]
    return len(sinir), etiketler[-1]


def yukseklik_kazanimi(conf: float) -> list[dict]:
    """Verilen esikte, kutu yuksekligi bandina gore taban ve model recall farki."""
    veri: dict[str, list[dict]] = {}
    for kosu_adi, (kutu_yolu, _, _) in KOSULAR.items():
        satirlar = list(csv.DictReader(Path(kutu_yolu).open(encoding="utf-8")))
        veri[kosu_adi] = [s for s in satirlar if abs(float(s["conf_esigi"]) - conf) < 1e-9]

    cikti: list[dict] = []
    for grup in GRUPLAR:
        for bant_no in range(len(YUKSEKLIK_SINIRLARI) + 1):
            hucre: dict[str, tuple[int, int]] = {}
            etiket = ""
            for kosu_adi, satirlar in veri.items():
                secilen = [
                    s for s in satirlar
                    if gruba_girer(s, grup)
                    and yukseklik_bandi(float(s["kutu_yukseklik_px"]))[0] == bant_no
                ]
                etiket = yukseklik_bandi(
                    float(secilen[0]["kutu_yukseklik_px"])
                )[1] if secilen else yukseklik_bandi(
                    YUKSEKLIK_SINIRLARI[bant_no] if bant_no < len(YUKSEKLIK_SINIRLARI)
                    else YUKSEKLIK_SINIRLARI[-1]
                )[1]
                hucre[kosu_adi] = (
                    sum(1 for s in secilen if s["eslesti"] == "1"), len(secilen)
                )

            (taban_tp, n), (model_tp, n2) = hucre["Taban-512"], hucre["Model-512"]
            if n == 0:
                continue
            assert n == n2, f"hedef sayisi uyusmuyor: {n} != {n2}"
            taban_r, model_r = taban_tp / n, model_tp / n
            cikti.append({
                "grup": grup,
                "yukseklik_bandi_px": etiket,
                "conf_esigi": conf,
                "hedef_sayisi": n,
                "taban_tp": taban_tp,
                "taban_recall": sayi_bicimle(taban_r),
                "model_tp": model_tp,
                "model_recall": sayi_bicimle(model_r),
                "fark_recall": sayi_bicimle(model_r - taban_r),
                "az_ornek": "az ornek" if n < AZ_ORNEK_SINIRI else "",
            })
    return cikti


def main() -> None:
    a = argparse.ArgumentParser(
        description="Kutu bazinda kayitlardan esik taramasi ve yukseklik bazli kazanim uretir. Yeni tarama yapmaz.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    a.add_argument("--adim", type=float, default=0.01, help="Esik tarama adimi")
    a.add_argument("--alt", type=float, default=0.05, help="En dusuk esik")
    a.add_argument("--ust", type=float, default=0.95, help="En yuksek esik")
    a.add_argument("--kazanim-conf", type=float, default=0.30, help="Yukseklik kazanimi icin esik")
    arg = a.parse_args()

    kosu = kosu_bilgisi(
        girdi="reports/test_kutu_bazinda.csv + reports/test_kutu_bazinda_model512.csv",
        tarama_notu="yeni model taramasi yapilmadi; mevcut kutu bazinda kayitlardan turetildi",
        recall_turetimi="eslesen_skor >= esik; olculmus uc esikte birebir dogrulandi",
        fp_turetimi=(
            "Model-512: tahminler_model512.csv'den turetildi (tum esikler dolu). "
            "Taban-512: tahmin kaydi alinmadigi icin yalnizca olculmus uc esikte dolu."
        ),
        az_ornek_siniri=AZ_ORNEK_SINIRI,
    )

    tarama = esik_taramasi(arg.adim, arg.alt, arg.ust)
    h1 = csv_yaz(RAPOR_KOK / "esik_taramasi.csv", tarama, kosu)

    kazanim = yukseklik_kazanimi(arg.kazanim_conf)
    h2 = csv_yaz(RAPOR_KOK / "yukseklik_kazanim.csv", kazanim, kosu)

    print(f"{h1}  ({len(tarama)} satir)")
    print(f"{h2}  ({len(kazanim)} satir)")


if __name__ == "__main__":
    main()
