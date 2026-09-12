"""COCO ile onceden egitilmis hazir bir dedektoru (yolo11n) SAHI karolamasiyla
calistirip taban cizgisi basarimini olcer. Model egitimi yapilmaz; sadece
"hazir model ne kadarini buluyor" sorusu yanitlanir."""

from __future__ import annotations

import argparse
import math
import sys
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
    etiket_yolu,
    goruntuleri_listele,
    karolamali_tara,
    kosu_bilgisi,
    kutulari_eslestir,
    model_kur,
    sayi_bicimle,
    tablo_bas,
    yolo_etiket_oku,
)

VARSAYILAN_MODEL = "yolo11n.pt"
VARSAYILAN_CONF = [0.05, 0.15, 0.30]

# --bolum hepsi verildiginde birlestirilecek bolumler; sira sabit tutulur ki
# goruntu listesi her calistirmada ayni olsun.
TUM_BOLUMLER = ["train", "valid", "test"]

# Ozet satirlarinda haric tutulan kaynak. ZRI (sehir parki) veri kumesindeki
# etiketlerin buyuk kismini tek basina tasidigi ve diger kaynaklardan belirgin
# sekilde farkli oldugu icin, onsuz bir ozet satiri da uretiliyor.
OZET_HARIC_ONEK = "ZRI"

# Uzun kosularda log dosyasina kac goruntude bir ilerleme satiri yazilacagi.
ILERLEME_ARALIGI = 50


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
    ayrastirici.add_argument(
        "--bolum", default="test",
        help="Olculecek bolum; 'hepsi' verilirse train+valid+test birlestirilir",
    )
    ayrastirici.add_argument(
        "--onek", nargs="+", default=None,
        help=(
            "Sadece bu kaynak oneklerine sahip goruntuler olculsun (or. VRD MED). "
            "Onek, dosya adinin ikinci parcasidir. Verilmezse tum onekler alinir."
        ),
    )
    ayrastirici.add_argument(
        "--onek-bazinda", action="store_true",
        help=(
            "Ciktiyi kaynak bazinda uretir: her onek x her conf esigi icin ayri "
            f"satir, ayrica TOPLAM ve {OZET_HARIC_ONEK}_HARIC ozet satirlari."
        ),
    )
    ayrastirici.add_argument("--limit", type=int, default=100, help="En fazla kac goruntu islensin (0 = hepsi)")
    ayrastirici.add_argument("--karo", type=int, default=512, help="Karo (slice) kenar uzunlugu, piksel")
    ayrastirici.add_argument("--ortusme", type=float, default=0.2, help="Karolar arasi ortusme orani")
    ayrastirici.add_argument("--conf", type=float, nargs="+", default=VARSAYILAN_CONF, help="Guven esikleri; her deger icin bir satir uretilir")
    ayrastirici.add_argument("--iou", type=float, default=0.3, help="Eslestirme icin IoU esigi")
    ayrastirici.add_argument("--model", default=VARSAYILAN_MODEL, help="Ultralytics model dosyasi")
    ayrastirici.add_argument("--cikti", type=Path, default=RAPOR_KOK / "taban_cizgisi.csv", help="Sonuc CSV dosyasinin yolu")
    ayrastirici.add_argument(
        "--kutu-cikti", type=Path, default=RAPOR_KOK / "kutu_bazinda_sonuc.csv",
        help=(
            "Her gercek kutunun eslesme sonucunun yazilacagi CSV. Toplu metrikler "
            "hangi kutunun neden kacirildigini saklamaz; bu dosya onu korur."
        ),
    )
    ayrastirici.add_argument(
        "--tahmin-kaydi", type=Path, default=None,
        help=(
            "Verilirse NMS sonrasi TUM tahminler (eslesen + eslesmeyen) bu CSV'ye "
            "yazilir. Kutu bazinda kayit yalnizca gercek kutulari tutar; FP'lerin "
            "esige gore nasil degistigi ancak bu dosyayla hesaplanabilir. "
            "Verilmezse hicbir sey yazilmaz ve diger ciktilar degismez."
        ),
    )
    ayrastirici.add_argument(
        "--dogrula", action="store_true",
        help=(
            "Tek-tarama-sonra-filtreleme optimizasyonunu dogrular: bir goruntuyu en "
            "yuksek conf ile dogrudan tarar ve sonucu, dusuk conf taramasinin ayni "
            "esikle filtrelenmis haliyle karsilastirir."
        ),
    )
    return ayrastirici.parse_args()


def onek_cikar(goruntu: Path) -> str:
    """Dosya adindan kaynak onegini cikarir: train_ZRI_3035_... -> ZRI"""
    parcalar = goruntu.stem.split("_")
    return parcalar[1] if len(parcalar) > 1 else "?"


def goruntuleri_topla(
    bolumler: list[str], veri_kok: Path, limit: int | None, onekler: list[str] | None
) -> list[tuple[Path, Path]]:
    """Verilen bolumlerdeki goruntuleri, istenen kaynak onekleriyle filtreleyerek
    (goruntu, etiket_dizini) ciftleri halinde toplar. Bolum ve dosya sirasi sabit
    oldugu icin ayni argumanlar her zaman ayni listeyi uretir."""
    secilen_onekler = {o.upper() for o in onekler} if onekler else None
    ciftler: list[tuple[Path, Path]] = []
    for bolum in bolumler:
        goruntu_dizin, etiket_dizin = bolum_yolu(bolum, veri_kok)
        for yol in goruntuleri_listele(goruntu_dizin):
            if secilen_onekler and onek_cikar(yol).upper() not in secilen_onekler:
                continue
            ciftler.append((yol, etiket_dizin))
    # Limit, bolumler birlestirildikten sonra toplam uzerinde uygulanir.
    if limit:
        ciftler = ciftler[:limit]
    return ciftler


def gercekleri_yukle_coklu(ciftler: list[tuple[Path, Path]]) -> dict[Path, list[Kutu]]:
    """Her goruntunun etiketlerini kendi bolumunun labels klasorunden okur; boylece
    birden fazla bolum birlestirildiginde de dogru etiket dosyasi kullanilir."""
    from PIL import Image

    gercekler: dict[Path, list[Kutu]] = {}
    for yol, etiket_dizin in ciftler:
        with Image.open(yol) as gorsel:
            genislik, yukseklik = gorsel.size
        gercekler[yol] = yolo_etiket_oku(etiket_yolu(yol, etiket_dizin), genislik, yukseklik)
    return gercekler


def goruntuleri_tara(
    model, goruntuler: list[Path], karo: int, ortusme: float
) -> tuple[dict[Path, list[Kutu]], float]:
    """Tum goruntuleri bir kez tarar; tahminleri ve toplam gecen sureyi dondurur.
    Tarama en dusuk guven esigiyle yapilir, yuksek esikler sonradan filtrelenir.
    Uzun kosularda log dosyasindan takip edilebilsin diye araliklarla ilerleme basar."""
    tahminler: dict[Path, list[Kutu]] = {}
    toplam = len(goruntuler)
    baslangic = time.perf_counter()

    # tqdm cubugu sadece terminalde anlamli; log dosyasina yazarken kapatiyoruz.
    terminalde = sys.stderr.isatty()
    for sira, yol in enumerate(
        tqdm(goruntuler, desc="tarama", unit="gor", disable=not terminalde), start=1
    ):
        tahminler[yol] = karolamali_tara(model, yol, karo, ortusme)

        if sira % ILERLEME_ARALIGI == 0 or sira == toplam:
            gecen = time.perf_counter() - baslangic
            hiz = gecen / sira
            kalan = hiz * (toplam - sira)
            satir = (f"  [{sira:5d}/{toplam}] %{100*sira/toplam:5.1f}  "
                     f"gecen {gecen/60:6.1f} dk  kalan ~{kalan/60:6.1f} dk  "
                     f"({hiz:.2f} sn/gor)")
            if terminalde:
                tqdm.write(satir)
            else:
                print(satir, flush=True)

    return tahminler, time.perf_counter() - baslangic


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


def kutu_bazinda_satirlar(
    gercekler: dict[Path, list[Kutu]],
    tahminler: dict[Path, list[Kutu]],
    ciftler: list[tuple[Path, Path]],
    conf_listesi: list[float],
    iou_esigi: float,
) -> list[dict]:
    """Her gercek kutu icin, her guven esiginde eslesip eslesmedigini tek tek
    kaydeder. Toplu metrikler yalnizca kac kutunun kacirildigini soyler; bu kayit
    HANGI kutunun kacirildigini ve o kutunun boyutunu da sakladigi icin, kosu
    tekrarlanmadan boyut/kaynak kirilimli analiz yapilabilmesini saglar."""
    bolum_haritasi = {yol: etiket_dizin.parent.name for yol, etiket_dizin in ciftler}
    satirlar: list[dict] = []

    for yol, gercek_kutular in gercekler.items():
        onek = onek_cikar(yol)
        bolum = bolum_haritasi.get(yol, "")
        for conf in conf_listesi:
            secilen = [k for k in tahminler.get(yol, []) if k.skor >= conf]
            eslesmeler, _, _ = kutulari_eslestir(gercek_kutular, secilen, iou_esigi)
            # gercek kutu indeksi -> (eslesen tahminin skoru, eslesme IoU'su)
            eslesme_haritasi = {
                g_idx: (secilen[t_idx].skor, iou) for g_idx, t_idx, iou in eslesmeler
            }
            for sira, kutu in enumerate(gercek_kutular):
                skor, iou_degeri = eslesme_haritasi.get(sira, (None, None))
                satirlar.append({
                    "goruntu": yol.name,
                    "bolum": bolum,
                    "kaynak_onek": onek,
                    "kutu_no": sira,
                    "kutu_genislik_px": sayi_bicimle(kutu.genislik, 1),
                    "kutu_yukseklik_px": sayi_bicimle(kutu.yukseklik, 1),
                    "kutu_alan_px2": sayi_bicimle(kutu.alan, 1),
                    "kutu_kenar_px": sayi_bicimle(math.sqrt(kutu.alan), 1),
                    "conf_esigi": conf,
                    "eslesti": int(skor is not None),
                    "eslesen_skor": sayi_bicimle(skor, 4) if skor is not None else "",
                    "eslesen_iou": sayi_bicimle(iou_degeri, 4) if iou_degeri is not None else "",
                })
    return satirlar


def tahmin_satirlari(
    gercekler: dict[Path, list[Kutu]],
    tahminler: dict[Path, list[Kutu]],
    ciftler: list[tuple[Path, Path]],
    conf: float,
    iou_esigi: float,
) -> list[dict]:
    """Taban esigindeki her tahmini TP/FP etiketiyle birlikte kaydeder.

    Eslestirme tahminleri skora gore AZALAN sirada gezer; esik yukseltmek yalnizca
    en dusuk skorlu tahminleri listeden atar ve daha yuksek skorlu tahminlerin
    atamasini degistirmez. Bu yuzden burada yazilan TP/FP etiketi, esigin uzerinde
    kalan her tahmin icin daha yuksek esiklerde de gecerlidir; FP/goruntu egrisi
    yeni tarama yapmadan bu dosyadan turetilebilir."""
    bolum_haritasi = {yol: etiket_dizin.parent.name for yol, etiket_dizin in ciftler}
    satirlar: list[dict] = []

    for yol, gercek_kutular in gercekler.items():
        secilen = [k for k in tahminler.get(yol, []) if k.skor >= conf]
        eslesmeler, _, _ = kutulari_eslestir(gercek_kutular, secilen, iou_esigi)
        # tahmin indeksi -> (eslesilen gercek kutu indeksi, IoU)
        tahmin_haritasi = {t_idx: (g_idx, iou) for g_idx, t_idx, iou in eslesmeler}

        for t_idx, kutu in enumerate(secilen):
            gercek_idx, iou_degeri = tahmin_haritasi.get(t_idx, (None, None))
            satirlar.append({
                "goruntu_adi": yol.name,
                "bolum": bolum_haritasi.get(yol, ""),
                "kaynak_onek": onek_cikar(yol),
                "skor": sayi_bicimle(kutu.skor, 4),
                "x1": sayi_bicimle(kutu.x1, 1),
                "y1": sayi_bicimle(kutu.y1, 1),
                "x2": sayi_bicimle(kutu.x2, 1),
                "y2": sayi_bicimle(kutu.y2, 1),
                "eslesme_durumu": "TP" if gercek_idx is not None else "FP",
                "eslesilen_gercek_kutu_id": gercek_idx if gercek_idx is not None else "",
                "eslesen_iou": sayi_bicimle(iou_degeri, 4) if iou_degeri is not None else "",
            })
    return satirlar


def metrik_satiri(
    ad: str,
    gercekler: dict[Path, list[Kutu]],
    tahminler: dict[Path, list[Kutu]],
    conf: float,
    iou_esigi: float,
    sure_goruntu_basina: float,
    onek_sutunu: bool,
) -> dict:
    """Bir goruntu alt kumesi ve tek bir conf esigi icin CSV satiri uretir."""
    metrik = esikte_degerlendir(gercekler, tahminler, conf, iou_esigi)
    satir: dict = {"kaynak_onek": ad} if onek_sutunu else {}
    satir.update({
        "conf_esigi": conf,
        "goruntu_sayisi": len(gercekler),
        "gercek_kutu": int(metrik["gercek_kutu"]),
        "dogru_bulunan_tp": int(metrik["dogru_bulunan_tp"]),
        "kacirilan_fn": int(metrik["kacirilan_fn"]),
        "recall": sayi_bicimle(metrik["recall"]),
        "yanlis_pozitif_fp": int(metrik["yanlis_pozitif_fp"]),
        "fp_goruntu_basina": sayi_bicimle(metrik["fp_goruntu_basina"], 2),
        "precision": sayi_bicimle(metrik["precision"]),
        "sure_saniye_goruntu_basina": sayi_bicimle(sure_goruntu_basina, 2),
    })
    return satir


def onek_bazinda_satirlar(
    gercekler: dict[Path, list[Kutu]],
    tahminler: dict[Path, list[Kutu]],
    conf_listesi: list[float],
    iou_esigi: float,
    sure_goruntu_basina: float,
) -> list[dict]:
    """Her kaynak onegi icin ayri, ayrica TOPLAM ve <onek>_HARIC ozet satirlari
    uretir. Onekler kutu sayisina gore azalan siralanir; esitlikte ad belirleyici."""
    onege_gore: dict[str, list[Path]] = {}
    for yol in gercekler:
        onege_gore.setdefault(onek_cikar(yol), []).append(yol)

    def alt_kume(yollar: list[Path]) -> tuple[dict, dict]:
        """Verilen goruntu yollari icin gercek ve tahmin sozluklerini daraltir."""
        kume = set(yollar)
        return (
            {y: k for y, k in gercekler.items() if y in kume},
            {y: k for y, k in tahminler.items() if y in kume},
        )

    sirali_onekler = sorted(
        onege_gore,
        key=lambda o: (-sum(len(gercekler[y]) for y in onege_gore[o]), o),
    )

    satirlar: list[dict] = []
    for onek in sirali_onekler:
        g, t = alt_kume(onege_gore[onek])
        for conf in conf_listesi:
            satirlar.append(
                metrik_satiri(onek, g, t, conf, iou_esigi, sure_goruntu_basina, True)
            )

    # Ozet satirlari: once tum kaynaklar, sonra baskin kaynak haric.
    for conf in conf_listesi:
        satirlar.append(
            metrik_satiri("TOPLAM", gercekler, tahminler, conf, iou_esigi,
                          sure_goruntu_basina, True)
        )

    haric_yollar = [y for y in gercekler if onek_cikar(y) != OZET_HARIC_ONEK]
    if haric_yollar and len(haric_yollar) < len(gercekler):
        g, t = alt_kume(haric_yollar)
        for conf in conf_listesi:
            satirlar.append(
                metrik_satiri(f"{OZET_HARIC_ONEK}_HARIC", g, t, conf, iou_esigi,
                              sure_goruntu_basina, True)
            )
    return satirlar


def main() -> None:
    """Goruntuleri tarar, metrikleri hesaplar, tabloyu basar ve CSV'ye yazar."""
    arg = argumanlari_coz()
    conf_listesi = sorted(arg.conf)
    en_dusuk_conf = conf_listesi[0]

    bolumler = TUM_BOLUMLER if arg.bolum == "hepsi" else [arg.bolum]
    ciftler = goruntuleri_topla(bolumler, arg.veri, arg.limit or None, arg.onek)
    if not ciftler:
        raise SystemExit(
            f"'{arg.bolum}' bolumunde "
            f"{('onek filtresi ' + ','.join(arg.onek) + ' ile ') if arg.onek else ''}"
            "goruntu bulunamadi."
        )
    goruntuler = [yol for yol, _ in ciftler]

    print(f"Bolum: {arg.bolum} ({'+'.join(bolumler)}) | Goruntu: {len(goruntuler)} | "
          f"Onek: {','.join(arg.onek) if arg.onek else 'hepsi'} | Karo: {arg.karo}px | "
          f"Ortusme: {arg.ortusme} | perform_standard_pred: {PERFORM_STANDARD_PRED} | "
          f"postprocess: {POSTPROCESS_TYPE}/{POSTPROCESS_MATCH_METRIC}")
    print(f"Tarama tek seferde conf={en_dusuk_conf} ile yapilir, yuksek esikler filtrelenir.")
    if len(bolumler) > 1:
        print("NOT: Bu kosu uc bolumu birlestiriyor. Model henuz egitilmedigi icin "
              "gecerlidir; egitimden sonra tekrarlanamaz.")
    print(flush=True)

    model = model_kur(arg.model, en_dusuk_conf)
    tahminler, toplam_sure = goruntuleri_tara(model, goruntuler, arg.karo, arg.ortusme)
    gercekler = gercekleri_yukle_coklu(ciftler)
    sure_goruntu_basina = toplam_sure / len(goruntuler)

    if arg.dogrula:
        optimizasyonu_dogrula(arg, goruntuler[0], tahminler[goruntuler[0]], conf_listesi[-1])

    if arg.onek_bazinda:
        satirlar = onek_bazinda_satirlar(
            gercekler, tahminler, conf_listesi, arg.iou, sure_goruntu_basina
        )
    else:
        satirlar = [
            metrik_satiri("", gercekler, tahminler, conf, arg.iou, sure_goruntu_basina, False)
            for conf in conf_listesi
        ]

    kosu = kosu_bilgisi(
        model=arg.model,
        bolum=arg.bolum,
        birlesik_bolumler="+".join(bolumler),
        onek_filtresi=",".join(arg.onek) if arg.onek else "hepsi",
        goruntu_sayisi=len(goruntuler),
        karo_boyutu=arg.karo,
        ortusme_orani=arg.ortusme,
        perform_standard_pred=PERFORM_STANDARD_PRED,
        postprocess_type=POSTPROCESS_TYPE,
        postprocess_match_metric=POSTPROCESS_MATCH_METRIC,
        iou_esigi=arg.iou,
        cihaz="cpu",
        tarama_notu=f"tek tarama conf={en_dusuk_conf}, yuksek esikler filtrelendi",
        gecerlilik_notu=(
            "Bu olcum train+valid+test bolumlerini birlestiriyor. Model henuz "
            "egitilmedigi ve hicbir goruntuyu gormedigi icin gecerlidir; Hafta 3'te "
            "egitim yapildiktan sonra bu kosu tekrarlanamaz."
            if len(bolumler) > 1 else "tek bolum olculdu"
        ),
    )
    hedef = csv_yaz(arg.cikti, satirlar, kosu)

    # Kutu bazinda kayit her kosuda uretilir. Tarama pahali oldugu icin (bu veri
    # kumesinde ~2.5 saat) sonuclarin ayrintisini atmak, ayni taramayi bastan
    # yapmak anlamina gelir; bu dosya bunu onler.
    kutu_satirlari = kutu_bazinda_satirlar(
        gercekler, tahminler, ciftler, conf_listesi, arg.iou
    )
    hedef_kutu = csv_yaz(arg.kutu_cikti, kutu_satirlari, kosu)

    # Tahmin kaydi yalnizca istenirse uretilir; varsayilan davranis degismez.
    hedef_tahmin = None
    if arg.tahmin_kaydi:
        tahmin_satir = tahmin_satirlari(
            gercekler, tahminler, ciftler, en_dusuk_conf, arg.iou
        )
        hedef_tahmin = csv_yaz(arg.tahmin_kaydi, tahmin_satir, kosu)

    print("\n=== TABAN CIZGISI (karolamali, SAHI) ===")
    tablo_bas(satirlar, [k for k in satirlar[0]])
    print(f"\nToplam tarama suresi: {toplam_sure/60:.1f} dk")
    print(f"CSV kaydedildi        : {hedef}")
    print(f"Kutu bazinda kayit    : {hedef_kutu}  ({len(kutu_satirlari)} satir)")
    if hedef_tahmin:
        print(f"Tahmin kaydi          : {hedef_tahmin}  ({len(tahmin_satir)} satir)")


if __name__ == "__main__":
    main()
