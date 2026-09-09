"""COCO ile onceden egitilmis hazir bir dedektoru (yolo11n) SAHI karolamasiyla
calistirip taban cizgisi basarimini olcer. Model egitimi yapilmaz; sadece
"hazir model ne kadarini buluyor" sorusu yanitlanir."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from tqdm import tqdm

from ortak import (
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
            "Hazir COCO modelini SAHI ile karolayarak calistirir ve taban cizgisi "
            "metriklerini olcer: gercek kutu sayisi, dogru bulunan (TP), kacirilan "
            "(FN), recall, yanlis pozitif (FP), goruntu basina FP, precision ve "
            "goruntu basina ortalama islem suresi. Verilen her guven esigi icin bir "
            "satir uretilir ve sonuc reports/taban_cizgisi.csv olarak kaydedilir."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Veri kumesi kok klasoru")
    ayrastirici.add_argument("--bolum", default="test", help="Olculecek bolum")
    ayrastirici.add_argument("--limit", type=int, default=100, help="En fazla kac goruntu islensin (0 = hepsi)")
    ayrastirici.add_argument("--karo", type=int, default=512, help="Karo (slice) kenar uzunlugu, piksel")
    ayrastirici.add_argument("--ortusme", type=float, default=0.2, help="Karolar arasi ortusme orani")
    ayrastirici.add_argument("--conf", type=float, nargs="+", default=VARSAYILAN_CONF, help="Guven esikleri; her deger icin bir satir uretilir")
    ayrastirici.add_argument("--iou", type=float, default=0.3, help="Eslestirme icin IoU esigi")
    ayrastirici.add_argument("--model", default=VARSAYILAN_MODEL, help="Ultralytics model dosyasi")
    ayrastirici.add_argument("--cikti", type=Path, default=RAPOR_KOK / "taban_cizgisi.csv", help="Sonuc CSV dosyasinin yolu")
    ayrastirici.add_argument(
        "--dogrula", action="store_true",
        help=(
            "Tek-tarama-sonra-filtreleme optimizasyonunu dogrular: bir goruntuyu en "
            "yuksek conf ile dogrudan tarar ve sonucu, dusuk conf taramasinin ayni "
            "esikle filtrelenmis haliyle karsilastirir."
        ),
    )
    return ayrastirici.parse_args()


def goruntuleri_tara(
    model, goruntuler: list[Path], karo: int, ortusme: float
) -> tuple[dict[Path, list[Kutu]], float]:
    """Tum goruntuleri bir kez tarar; tahminleri ve toplam gecen suryi dondurur.
    Tarama en dusuk guven esigiyle yapilir, yuksek esikler sonradan filtrelenir."""
    tahminler: dict[Path, list[Kutu]] = {}
    baslangic = time.perf_counter()
    for yol in tqdm(goruntuler, desc="tarama", unit="gor"):
        tahminler[yol] = karolamali_tara(model, yol, karo, ortusme)
    gecen = time.perf_counter() - baslangic
    return tahminler, gecen


def optimizasyonu_dogrula(
    arg, goruntu_yolu: Path, dusuk_conf_tahminleri: list[Kutu], yuksek_conf: float
) -> bool:
    """Tek tarama + sonradan filtreleme sonucunun, dogrudan yuksek esikli taramayla
    ayni kutulari verdigini tek bir goruntu uzerinde dogrular."""
    print(f"\n=== OPTIMIZASYON DOGRULAMASI ({goruntu_yolu.name}) ===")
    dogrudan_model = model_kur(arg.model, yuksek_conf)
    dogrudan = karolamali_tara(dogrudan_model, goruntu_yolu, arg.karo, arg.ortusme)
    filtreli = [k for k in dusuk_conf_tahminleri if k.skor >= yuksek_conf]

    def anahtar(kutular: list[Kutu]):
        """Kutu listesini karsilastirilabilir, sirali bir imzaya cevirir."""
        return sorted(
            (round(k.x1, 2), round(k.y1, 2), round(k.x2, 2), round(k.y2, 2), round(k.skor, 4))
            for k in kutular
        )

    dogrudan_imza, filtreli_imza = anahtar(dogrudan), anahtar(filtreli)
    ayni = dogrudan_imza == filtreli_imza

    print(f"  dogrudan conf={yuksek_conf} tarama : {len(dogrudan)} kutu")
    print(f"  conf={min(arg.conf)} tarama + filtre: {len(filtreli)} kutu")
    if ayni:
        print("  SONUC: AYNI -> tek tarama + filtreleme optimizasyonu guvenli.")
    else:
        print("  SONUC: FARKLI -> kutu birlestirme (postprocess) esikten etkileniyor.")
        print("         postprocess_type='NMS' denenmeli.")
        for ad, imza in (("sadece dogrudanda", set(dogrudan_imza) - set(filtreli_imza)),
                         ("sadece filtrelide", set(filtreli_imza) - set(dogrudan_imza))):
            if imza:
                print(f"         {ad}: {len(imza)} kutu, ornek: {sorted(imza)[0]}")
    return ayni


def main() -> None:
    """Goruntuleri tarar, her guven esigi icin metrikleri hesaplar, tabloyu basar ve CSV'ye yazar."""
    arg = argumanlari_coz()
    conf_listesi = sorted(arg.conf)
    en_dusuk_conf = conf_listesi[0]

    goruntu_dizin, etiket_dizin = bolum_yolu(arg.bolum, arg.veri)
    goruntuler = goruntuleri_listele(goruntu_dizin, arg.limit or None)
    if not goruntuler:
        raise SystemExit(f"'{arg.bolum}' bolumunde goruntu bulunamadi.")

    print(f"Bolum: {arg.bolum} | Goruntu: {len(goruntuler)} | Karo: {arg.karo}px | "
          f"Ortusme: {arg.ortusme} | perform_standard_pred: {PERFORM_STANDARD_PRED} | "
          f"postprocess: {POSTPROCESS_TYPE}/{POSTPROCESS_MATCH_METRIC}")
    print(f"Tarama tek seferde conf={en_dusuk_conf} ile yapilir, yuksek esikler filtrelenir.\n")

    model = model_kur(arg.model, en_dusuk_conf)
    tahminler, toplam_sure = goruntuleri_tara(model, goruntuler, arg.karo, arg.ortusme)
    gercekler = gercekleri_yukle(goruntuler, etiket_dizin)
    sure_goruntu_basina = toplam_sure / len(goruntuler)

    if arg.dogrula:
        optimizasyonu_dogrula(arg, goruntuler[0], tahminler[goruntuler[0]], conf_listesi[-1])

    satirlar: list[dict] = []
    for conf in conf_listesi:
        metrik = esikte_degerlendir(gercekler, tahminler, conf, arg.iou)
        satirlar.append({
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
        iou_esigi=arg.iou,
        cihaz="cpu",
        tarama_notu=f"tek tarama conf={en_dusuk_conf}, yuksek esikler filtrelendi",
    )
    hedef = csv_yaz(arg.cikti, satirlar, kosu)

    print("\n=== TABAN CIZGISI (karolamali, SAHI) ===")
    tablo_bas(satirlar)
    print(f"\nToplam tarama suresi: {toplam_sure:.1f} sn")
    print(f"CSV kaydedildi: {hedef}")


if __name__ == "__main__":
    main()
