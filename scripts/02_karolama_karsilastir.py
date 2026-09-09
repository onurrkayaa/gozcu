"""Ayni goruntu kumesini iki farkli sekilde tarayip karolamanin katkisini olcer:
(a) karolamali -- SAHI ile 512 piksel karolar, (b) karolamasiz -- tum goruntu
dogrudan modele verilir ve model onu kendi giris boyutuna (640) kucultur."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from tqdm import tqdm

from ortak import (
    KAROLAMASIZ_GIRIS,
    PERFORM_STANDARD_PRED,
    POSTPROCESS_MATCH_METRIC,
    POSTPROCESS_TYPE,
    RAPOR_KOK,
    VERI_KOK,
    Kutu,
    bolum_yolu,
    csv_yaz,
    esikte_degerlendir,
    gercekleri_yukle,
    goruntuleri_listele,
    karolamali_tara,
    karolamasiz_tara,
    kosu_bilgisi,
    model_kur,
    sayi_bicimle,
    tablo_bas,
)

VARSAYILAN_MODEL = "yolo11n.pt"
VARSAYILAN_CONF = [0.05, 0.15, 0.30]


def argumanlari_coz() -> argparse.Namespace:
    """Komut satiri argumanlarini tanimlar ve cozer."""
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Karolamali (SAHI, 512px karolar) ve karolamasiz (tum goruntu, model "
            "icinde 640'a kucultulur) taramayi ayni goruntuler uzerinde olcup tek "
            "tabloda karsilastirir. Her mod ve her guven esigi icin bir satir "
            "uretilir; sonuc reports/karolama_karsilastirma.csv olarak kaydedilir."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Veri kumesi kok klasoru")
    ayrastirici.add_argument("--bolum", default="test", help="Olculecek bolum")
    ayrastirici.add_argument("--limit", type=int, default=100, help="En fazla kac goruntu islensin (0 = hepsi)")
    ayrastirici.add_argument("--karo", type=int, default=512, help="Karolamali moddaki karo kenar uzunlugu, piksel")
    ayrastirici.add_argument("--ortusme", type=float, default=0.2, help="Karolar arasi ortusme orani")
    ayrastirici.add_argument("--conf", type=float, nargs="+", default=VARSAYILAN_CONF, help="Guven esikleri")
    ayrastirici.add_argument("--iou", type=float, default=0.3, help="Eslestirme icin IoU esigi")
    ayrastirici.add_argument("--model", default=VARSAYILAN_MODEL, help="Ultralytics model dosyasi")
    ayrastirici.add_argument(
        "--cikti", type=Path, default=RAPOR_KOK / "karolama_karsilastirma.csv",
        help="Sonuc CSV dosyasinin yolu",
    )
    return ayrastirici.parse_args()


def modu_tara(
    model, goruntuler: list[Path], mod: str, karo: int, ortusme: float
) -> tuple[dict[Path, list[Kutu]], float]:
    """Verilen modda (karolamali/karolamasiz) tum goruntuleri bir kez tarar ve
    tahminlerle birlikte gecen toplam sureyi dondurur."""
    tahminler: dict[Path, list[Kutu]] = {}
    baslangic = time.perf_counter()
    for yol in tqdm(goruntuler, desc=f"{mod:12}", unit="gor"):
        if mod == "karolamali":
            tahminler[yol] = karolamali_tara(model, yol, karo, ortusme)
        else:
            tahminler[yol] = karolamasiz_tara(model, yol)
    return tahminler, time.perf_counter() - baslangic


def main() -> None:
    """Iki modu da calistirir, her mod ve esik icin metrikleri hesaplar, tabloyu
    basar ve karsilastirmayi CSV'ye yazar."""
    arg = argumanlari_coz()
    conf_listesi = sorted(arg.conf)
    en_dusuk_conf = conf_listesi[0]

    goruntu_dizin, etiket_dizin = bolum_yolu(arg.bolum, arg.veri)
    goruntuler = goruntuleri_listele(goruntu_dizin, arg.limit or None)
    if not goruntuler:
        raise SystemExit(f"'{arg.bolum}' bolumunde goruntu bulunamadi.")

    print(f"Bolum: {arg.bolum} | Goruntu: {len(goruntuler)} | IoU esigi: {arg.iou}")
    print(f"(a) karolamali  : {arg.karo}px karo, ortusme {arg.ortusme}, "
          f"perform_standard_pred={PERFORM_STANDARD_PRED}, "
          f"postprocess={POSTPROCESS_TYPE}/{POSTPROCESS_MATCH_METRIC}")
    print(f"(b) karolamasiz : tum goruntu tek parca, model {KAROLAMASIZ_GIRIS}px'e kucultur\n")

    gercekler = gercekleri_yukle(goruntuler, etiket_dizin)
    model = model_kur(arg.model, en_dusuk_conf)

    satirlar: list[dict] = []
    for mod in ("karolamali", "karolamasiz"):
        tahminler, toplam_sure = modu_tara(model, goruntuler, mod, arg.karo, arg.ortusme)
        sure_goruntu_basina = toplam_sure / len(goruntuler)
        for conf in conf_listesi:
            metrik = esikte_degerlendir(gercekler, tahminler, conf, arg.iou)
            satirlar.append({
                "mod": mod,
                "conf_esigi": conf,
                "gercek_kutu": int(metrik["gercek_kutu"]),
                "dogru_bulunan_tp": int(metrik["dogru_bulunan_tp"]),
                "kacirilan_fn": int(metrik["kacirilan_fn"]),
                "recall": sayi_bicimle(metrik["recall"]),
                "yanlis_pozitif_fp": int(metrik["yanlis_pozitif_fp"]),
                "fp_goruntu_basina": sayi_bicimle(metrik["fp_goruntu_basina"], 2),
                "precision": sayi_bicimle(metrik["precision"]),
                "sure_saniye_goruntu_basina": sayi_bicimle(sure_goruntu_basina, 2),
            })

    kosu = kosu_bilgisi(
        model=arg.model,
        bolum=arg.bolum,
        goruntu_sayisi=len(goruntuler),
        karo_boyutu=arg.karo,
        ortusme_orani=arg.ortusme,
        perform_standard_pred=PERFORM_STANDARD_PRED,
        postprocess_type=POSTPROCESS_TYPE,
        postprocess_match_metric=POSTPROCESS_MATCH_METRIC,
        karolamasiz_giris=KAROLAMASIZ_GIRIS,
        iou_esigi=arg.iou,
        cihaz="cpu",
        tarama_notu=f"her mod tek tarama conf={en_dusuk_conf}, yuksek esikler filtrelendi",
    )
    hedef = csv_yaz(arg.cikti, satirlar, kosu)

    print("\n=== KAROLAMALI vs KAROLAMASIZ ===")
    tablo_bas(satirlar)

    # Karolamanin recall kazancini esik basina ozetleyerek tabloyu yorumlamayi kolaylastiriyoruz.
    print("\n=== RECALL KAZANCI (karolamali - karolamasiz) ===")
    karsilastirma = []
    for conf in conf_listesi:
        a = next(s for s in satirlar if s["mod"] == "karolamali" and s["conf_esigi"] == conf)
        b = next(s for s in satirlar if s["mod"] == "karolamasiz" and s["conf_esigi"] == conf)
        karsilastirma.append({
            "conf_esigi": conf,
            "recall_karolamali": a["recall"],
            "recall_karolamasiz": b["recall"],
            "recall_farki": sayi_bicimle(a["recall"] - b["recall"]),
            "tp_karolamali": a["dogru_bulunan_tp"],
            "tp_karolamasiz": b["dogru_bulunan_tp"],
        })
    tablo_bas(karsilastirma)

    print(f"\nCSV kaydedildi: {hedef}")


if __name__ == "__main__":
    main()
