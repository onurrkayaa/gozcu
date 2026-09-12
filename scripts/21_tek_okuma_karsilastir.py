"""Iki gercek Celery sure olcumunu (once/sonra) karsilastirir.

YENI TARAMA YAPMAZ. Girdisi yalnizca daha onceki iki kosunun kare bazinda
CSV'leridir; yuzde degisimleri iki OLCULMUS degerden burada hesaplanir, sohbette
degil.

Kuyruk bekleme AYRI raporlanir: o sure iscinin sirasini bekleme suresidir,
kod optimizasyonunun kazanimi degildir.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

SCRIPT_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIZIN))

import importlib.util  # noqa: E402

from ortak import RAPOR_KOK, csv_yaz, kosu_bilgisi, sayi_bicimle, tablo_bas  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "celery_sure", SCRIPT_DIZIN / "19_gercek_onnx_celery_sure.py"
)
SURE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SURE)

# Kod degisikliginin etkisinin arandigi alanlar.
CALISMA_ALANLARI = (
    "goruntu_okuma", "onnx_cikarim", "nms_koordinat", "db_yazma",
    "frame_toplam", "uctan_uca_sure",
)
# Isci zamanlamasina bagli oldugu icin ayri tutulan alan.
KUYRUK_ALANI = "kuyruk_bekleme"


def argumanlari_coz() -> argparse.Namespace:
    a = argparse.ArgumentParser(
        description="Iki sure olcumunun kare CSV'lerinden once/sonra tablosu uretir.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    a.add_argument("--once", type=Path, default=RAPOR_KOK / "gercek_onnx_celery_sure.csv")
    a.add_argument("--sonra", type=Path, default=RAPOR_KOK / "gercek_onnx_celery_sure_tek_okuma.csv")
    a.add_argument("--cikti", type=Path, default=RAPOR_KOK / "tek_okuma_karsilastirma.csv")
    return a.parse_args()


def satirlari_oku(yol: Path) -> list[dict]:
    if not yol.is_file():
        raise SystemExit(f"Olcum CSV'si bulunamadi: {yol}")
    return list(csv.DictReader(yol.open(encoding="utf-8")))


def degerler(satirlar: list[dict], alan: str) -> list[float]:
    return [float(s[alan]) for s in satirlar if s[alan] not in ("", "olculmedi")]


def istatistik(degerler_listesi: list[float]) -> dict:
    if not degerler_listesi:
        return {ad: "olculmedi" for ad in ("minimum", "medyan", "p95", "maksimum")}
    return {
        "minimum": sayi_bicimle(min(degerler_listesi), 4),
        "medyan": sayi_bicimle(SURE.medyan(degerler_listesi), 4),
        "p95": sayi_bicimle(SURE.yuzdelik(degerler_listesi, 0.95), 4),
        "maksimum": sayi_bicimle(max(degerler_listesi), 4),
    }


def yuzde_degisim(once: float | str, sonra: float | str) -> float | str:
    """Iki olculmus degerden yuzde degisim; biri yoksa 'olculmedi'."""
    if once in ("olculmedi", "") or sonra in ("olculmedi", "") or float(once) == 0:
        return "olculmedi"
    return sayi_bicimle(100 * (float(sonra) - float(once)) / float(once), 2)


def karsilastirma_satirlari(once: list[dict], sonra: list[dict], alanlar) -> list[dict]:
    """Her alan icin once/sonra istatistikleri ve yuzde degisimleri."""
    satirlar = []
    for alan in alanlar:
        o = istatistik(degerler(once, alan))
        s = istatistik(degerler(sonra, alan))
        satir = {"olcu": alan, "once_olcum_sayisi": len(degerler(once, alan)),
                 "sonra_olcum_sayisi": len(degerler(sonra, alan))}
        for ad in ("minimum", "medyan", "p95", "maksimum"):
            satir[f"once_{ad}"] = o[ad]
            satir[f"sonra_{ad}"] = s[ad]
            satir[f"degisim_yuzde_{ad}"] = yuzde_degisim(o[ad], s[ad])
        satirlar.append(satir)
    return satirlar


def kosu_ozeti(satirlar: list[dict]) -> dict:
    """Bir kosunun kare sayisi, tespit toplami ve oturum davranisi."""
    soguk = [s for s in satirlar if s["soguk_baslangic"] == "evet"]
    sicak = [s for s in satirlar if s["soguk_baslangic"] == "hayir"]
    sureler = [float(s["frame_toplam"]) for s in sicak if s["frame_toplam"] != "olculmedi"]
    sira = [int(s["surec_kare_sirasi"]) for s in satirlar if s["surec_kare_sirasi"] not in ("", "olculmedi")]
    return {
        "kare_sayisi": len(satirlar),
        "toplam_detection": sum(int(s["tespit_sayisi"]) for s in satirlar),
        "soguk_baslangic_sayisi": len(soguk),
        "soguk_ilk_kare_suresi": max(
            [float(s["frame_toplam"]) for s in soguk if s["frame_toplam"] != "olculmedi"] or ["olculmedi"]
        ),
        "soguk_haric_frame_medyan": sayi_bicimle(SURE.medyan(sureler), 4) if sureler else "olculmedi",
        "ayni_oturumda_en_cok_kare": max(sira) if sira else "olculmedi",
        "done_kare": sum(1 for s in satirlar if s["frame_durumu"] == "done"),
        "hatali_kare": sum(1 for s in satirlar if s["hata_sinifi"]),
    }


def main() -> None:
    arg = argumanlari_coz()
    once = satirlari_oku(arg.once)
    sonra = satirlari_oku(arg.sonra)

    calisma = karsilastirma_satirlari(once, sonra, CALISMA_ALANLARI)
    kuyruk = karsilastirma_satirlari(once, sonra, (KUYRUK_ALANI,))
    for satir in kuyruk:
        satir["not"] = (
            "isci zamanlamasina ve gorev sirasina bagli; kod kazanimi olarak "
            "yorumlanamaz"
        )
    for satir in calisma:
        satir["not"] = "kare icinde gecen calisma suresi"

    o_ozet, s_ozet = kosu_ozeti(once), kosu_ozeti(sonra)
    ozet_satiri = {
        "olcu": "KOSU OZETI", "not": "sayimlar, sure degil",
        "once_olcum_sayisi": o_ozet["kare_sayisi"], "sonra_olcum_sayisi": s_ozet["kare_sayisi"],
    }
    for ad in o_ozet:
        ozet_satiri[f"once_{ad}"] = o_ozet[ad]
        ozet_satiri[f"sonra_{ad}"] = s_ozet[ad]

    # Ozet satirinin sutunlari sure satirlarindakinden farkli; csv_yaz ilk
    # satirin anahtarlarini baslik sayiyor, bu yuzden birlesik anahtar kumesini
    # butun satirlara yayiyoruz (eksik alan bos kalir).
    tum = calisma + kuyruk + [ozet_satiri]
    basliklar = []
    for satir in tum:
        for ad in satir:
            if ad not in basliklar:
                basliklar.append(ad)
    tum = [{ad: satir.get(ad, "") for ad in basliklar} for satir in tum]
    kosu = kosu_bilgisi(
        girdi=f"{arg.once.as_posix()} + {arg.sonra.as_posix()}",
        once_gorev=once[0]["gorev_adi"],
        sonra_gorev=sonra[0]["gorev_adi"],
        once_sha256=once[0]["kosu_onnx_sha256"],
        sonra_sha256=sonra[0]["kosu_onnx_sha256"],
        tarama_notu="yeni tarama yapilmadi; iki kosunun kare bazinda CSV'lerinden turetildi",
        kuyruk_notu=(
            "kuyruk_bekleme ayri satirda; isci zamanlamasina bagli oldugu icin "
            "kod kazanimi sayilmaz"
        ),
    )
    cikti = csv_yaz(arg.cikti, tum, kosu)

    print("=== CALISMA SURELERI (once -> sonra, %) ===")
    tablo_bas(calisma, [
        "olcu", "once_medyan", "sonra_medyan", "degisim_yuzde_medyan",
        "once_p95", "sonra_p95", "degisim_yuzde_p95",
        "once_maksimum", "sonra_maksimum", "degisim_yuzde_maksimum",
    ])
    print("\n=== KUYRUK BEKLEME (ayri; kod kazanimi degil) ===")
    tablo_bas(kuyruk, ["olcu", "once_medyan", "sonra_medyan", "degisim_yuzde_medyan"])
    print("\n=== KOSU OZETI ===")
    tablo_bas([
        {"olcu": ad, "once": o_ozet[ad], "sonra": s_ozet[ad]} for ad in o_ozet
    ])
    print(f"\nCSV: {cikti}  ({len(tum)} satir)")


if __name__ == "__main__":
    main()
