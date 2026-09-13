#!/usr/bin/env python3
"""Esit FP butcesinde iki modelin yanlis pozitiflerini ve kontrol bolgelerini secer.

Ne yapar:

1. Iki modelin NMS sonrasi tahmin kaydini okur ve TP/FP toplamlarini mevcut
   olcum CSV'leriyle capraz kontrol eder. Uyusmazsa durur.
2. Tabanin OLCULMUS calisma noktasindan (conf 0,30) FP/goruntu butcesini alir,
   Model-512'nin ayni butceye en yakin esigini tarayarak bulur.
3. Her modelin calisma noktasindaki FP'lerinden protokoldeki katmanli
   ornekleme ile aday secer.
4. Her secilen FP icin AYNI GORUNTUDEN esleştirilmis bir kontrol bolgesi uretir.
5. FP ve kontrol adaylarini karistirip kor kimlik verir; manifest ile korleme
   anahtarini AYRI dosyalara yazar.

Protokol: reports/hafta7_fp_protokolu.md. Buradaki esikler, katsayilar ve
ornek buyuklukleri o dosyada sabitlenmis KARARLARDIR; olcumden turetilmedi.

Bu script YENI CIKARIM YAPMAZ. Tahmin kayitlari zaten uretilmis olmalidir.
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ortak import (  # noqa: E402
    RAPOR_KOK,
    VERI_KOK,
    Kutu,
    bolum_yolu,
    goruntuleri_listele,
    etiket_yolu,
    yolo_etiket_oku,
    iou_hesapla,
    kutulari_eslestir,
    kosu_bilgisi,
    csv_yaz,
    sayi_bicimle,
)

# --- Protokolde sabitlenen kararlar ------------------------------------------
TOHUM = 20260913
ESLESTIRME_IOU = 0.3
TABAN_CALISMA_ESIGI = 0.30
ORTUSEN_FP_IOU = 0.5          # iki FP birbiriyle bu kadar ortusurse biri elenir
KONTROL_TAHMIN_IOU = 0.1      # kontrol, modelin tahminleriyle bundan fazla ortusemez
KONTROL_DENEME = 200
MODEL_BASINA_HEDEF = 110
KATMAN_TABANI = 55            # bu sayidan az FP'si olan kaynagin tamami alinir
SIKI_PAY_ORANI = 0.10
SIKI_ASGARI_KENAR = 64
BAGLAM_KATSAYI = 8
BAGLAM_ASGARI_KENAR = 512
KALITE_ORANI = 0.10           # yeniden-test icin ayrilan pay

CAPRAZ_ESIKLER = (0.05, 0.15, 0.30)


def argumanlari_al():
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--veri", type=Path, default=VERI_KOK)
    a.add_argument("--bolum", default="test")
    a.add_argument("--taban-tahmin", type=Path,
                   default=RAPOR_KOK / "tahminler_taban512_hafta7.csv")
    a.add_argument("--model-tahmin", type=Path,
                   default=RAPOR_KOK / "tahminler_model512.csv")
    a.add_argument("--taban-ozet", type=Path, default=RAPOR_KOK / "test_taban_cizgisi.csv")
    a.add_argument("--model-ozet", type=Path, default=RAPOR_KOK / "test_model512.csv")
    a.add_argument("--aday-cikti", type=Path,
                   default=RAPOR_KOK / "hafta7_esit_fp_adaylari.csv")
    a.add_argument("--manifest-cikti", type=Path,
                   default=RAPOR_KOK / "hafta7_fp_etiket_manifesti.csv")
    a.add_argument("--anahtar-cikti", type=Path,
                   default=RAPOR_KOK / "hafta7_fp_korleme_anahtari.csv")
    return a.parse_args()


# --- Okuma --------------------------------------------------------------------

def tahmin_kaydi_oku(yol: Path) -> tuple[dict[str, list[Kutu]], dict[str, str]]:
    """Tahmin kaydini {goruntu_adi: [Kutu...]} ve kosu bilgisi olarak dondurur."""
    if not yol.is_file():
        raise FileNotFoundError(f"Tahmin kaydi yok: {yol}")
    kutular: dict[str, list[Kutu]] = defaultdict(list)
    kosu: dict[str, str] = {}
    with yol.open(encoding="utf-8") as dosya:
        for satir in csv.DictReader(dosya):
            kutular[satir["goruntu_adi"]].append(
                Kutu(float(satir["x1"]), float(satir["y1"]),
                     float(satir["x2"]), float(satir["y2"]),
                     skor=float(satir["skor"]))
            )
            if not kosu:
                kosu = {k: v for k, v in satir.items() if k.startswith("kosu_")}
    # Skora gore azalan, esitlikte koordinat sirasi: eslestirme deterministik olsun.
    for ad in kutular:
        kutular[ad].sort(key=lambda k: (-k.skor, k.x1, k.y1))
    return dict(kutular), kosu


def gercekleri_oku(veri_kok: Path, bolum: str) -> dict[str, tuple[list[Kutu], int, int]]:
    """{goruntu_adi: (gercek kutular, genislik, yukseklik)}."""
    from PIL import Image

    goruntu_dizin, etiket_dizin = bolum_yolu(bolum, veri_kok)
    sonuc: dict[str, tuple[list[Kutu], int, int]] = {}
    for yol in goruntuleri_listele(goruntu_dizin, limit=0):
        with Image.open(yol) as gorsel:
            g, y = gorsel.size
        sonuc[yol.name] = (yolo_etiket_oku(etiket_yolu(yol, etiket_dizin), g, y), g, y)
    return sonuc


def onek_cikar(goruntu_adi: str) -> str:
    parcalar = Path(goruntu_adi).stem.split("_")
    return parcalar[1] if len(parcalar) > 1 else "?"


# --- Degerlendirme ------------------------------------------------------------

def esikte_isaretle(gercekler, tahminler, esik):
    """Verilen esikte her goruntu icin (secilen tahminler, TP/FP bayraklari, IoU)."""
    cikti = {}
    for ad, (gercek_kutular, _g, _y) in gercekler.items():
        secilen = [k for k in tahminler.get(ad, []) if k.skor >= esik]
        eslesmeler, _, _ = kutulari_eslestir(gercek_kutular, secilen, ESLESTIRME_IOU)
        harita = {t: (g, iou) for g, t, iou in eslesmeler}
        cikti[ad] = (secilen, harita)
    return cikti


def esik_ozeti(gercekler, tahminler, esik):
    tp = fn = fp = 0
    isaretli = esikte_isaretle(gercekler, tahminler, esik)
    for ad, (gercek_kutular, _g, _y) in gercekler.items():
        secilen, harita = isaretli[ad]
        tp += len(harita)
        fn += len(gercek_kutular) - len(harita)
        fp += len(secilen) - len(harita)
    goruntu = len(gercekler)
    return {
        "tp": tp, "fn": fn, "fp": fp,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "fp_goruntu_basina": fp / goruntu if goruntu else 0.0,
    }


def ozet_csv_oku(yol: Path) -> dict[float, dict]:
    """Ozet CSV'nin TOPLAM satirlarini {conf: satir} olarak dondurur."""
    satirlar = {}
    with yol.open(encoding="utf-8") as dosya:
        for satir in csv.DictReader(dosya):
            ad = satir.get("kaynak_onek", "TOPLAM") or "TOPLAM"
            if ad != "TOPLAM":
                continue
            satirlar[round(float(satir["conf_esigi"]), 4)] = satir
    return satirlar


def sinirdaki_tahmin_sayisi(tahminler, esik) -> int:
    """Saklanan skoru esige TAM esit olan tahmin sayisi.

    Tahmin kaydindaki skorlar dort basamaga yuvarlanmis olarak saklanir. Ham
    skoru esigin hemen altinda olan bir tahmin, yuvarlandiktan sonra esige esit
    gorunur ve `skor >= esik` kuralindan gecer. Bu sayi, iki olcum arasindaki
    farkin yuvarlamayla aciklanip aciklanamayacaginin ust sinirini verir.
    """
    return sum(1 for kutular in tahminler.values()
               for kutu in kutular if abs(kutu.skor - esik) < 1e-12)


def capraz_kontrol(etiket, gercekler, tahminler, ozet_yolu: Path) -> list[dict]:
    """Tahmin kaydindan turetilen TP/FP'yi olculmus ozet CSV ile karsilastirir.

    Tam esitlik aranir. Tek istisna, protokolde yazili yuvarlama siniri:
    fark HESAPLANAN LEHINE ise ve buyuklugu, skoru esige tam esit olan tahmin
    sayisini asmiyorsa kontrol gecer ve durum acikca kaydedilir. Bunun disinda
    her fark analizi durdurur.
    """
    beklenen = ozet_csv_oku(ozet_yolu)
    satirlar = []
    for esik in CAPRAZ_ESIKLER:
        hesap = esik_ozeti(gercekler, tahminler, esik)
        ref = beklenen.get(round(esik, 4))
        if ref is None:
            satirlar.append({"model": etiket, "conf": esik, "durum": "referans yok"})
            continue
        olculmus_tp, olculmus_fp = int(ref["dogru_bulunan_tp"]), int(ref["yanlis_pozitif_fp"])
        fark_tp, fark_fp = hesap["tp"] - olculmus_tp, hesap["fp"] - olculmus_fp
        sinir = sinirdaki_tahmin_sayisi(tahminler, esik)
        if fark_tp == 0 and fark_fp == 0:
            durum = "uyustu"
        elif fark_tp >= 0 and fark_fp >= 0 and 0 < fark_tp + fark_fp <= sinir:
            durum = "yuvarlama siniri ile aciklandi"
        else:
            durum = "UYUSMADI"
        satirlar.append({
            "model": etiket, "conf": esik,
            "tahmin_kaydindan_tp": hesap["tp"], "olculmus_tp": olculmus_tp,
            "tahmin_kaydindan_fp": hesap["fp"], "olculmus_fp": olculmus_fp,
            "sinirdaki_tahmin": sinir,
            "durum": durum,
        })
    return satirlar


def butceye_en_yakin_esik(gercekler, tahminler, butce) -> tuple[float, dict, list[dict]]:
    """|FP/goruntu - butce| degerini en kucuk yapan esik; esitlikte BUYUK esik."""
    egri = []
    en_iyi = None
    for adim in range(5, 96):
        esik = adim / 100.0
        ozet = esik_ozeti(gercekler, tahminler, esik)
        fark = abs(ozet["fp_goruntu_basina"] - butce)
        egri.append({"conf": esik, "fp_goruntu_basina": sayi_bicimle(ozet["fp_goruntu_basina"], 4),
                     "fp": ozet["fp"], "tp": ozet["tp"],
                     "recall": sayi_bicimle(ozet["recall"], 4),
                     "butce_farki": sayi_bicimle(fark, 4)})
        # Esitlikte buyuk esik kazanir: sirali taramada >= ile guncelleyerek.
        if en_iyi is None or fark < en_iyi[1] - 1e-12 or abs(fark - en_iyi[1]) <= 1e-12:
            en_iyi = (esik, fark, ozet)
    return en_iyi[0], en_iyi[2], egri


# --- Kontrol bolgesi ----------------------------------------------------------

def kontrol_bolgesi_bul(rastgele, kutu: Kutu, gercek_kutular, tum_tahminler,
                        genislik, yukseklik):
    """FP ile ayni olculerde, gercek insanlarla ve tahminlerle cakismayan bolge.

    Icerige BAKILMAZ: secim yalnizca geometriktir. Icerige bakarak secmek
    kontrolu 'insan faaliyeti olmayan yer' haline getirir ve karsilastirmayi
    bastan bozar.
    """
    g = kutu.genislik
    y = kutu.yukseklik
    if g <= 0 or y <= 0 or g >= genislik or y >= yukseklik:
        return None
    for _ in range(KONTROL_DENEME):
        x1 = rastgele.uniform(0, genislik - g)
        y1 = rastgele.uniform(0, yukseklik - y)
        aday = Kutu(x1, y1, x1 + g, y1 + y)
        if any(iou_hesapla(aday, gercek) > 0 for gercek in gercek_kutular):
            continue
        if any(gercek.x1 <= (x1 + g / 2) <= gercek.x2
               and gercek.y1 <= (y1 + y / 2) <= gercek.y2 for gercek in gercek_kutular):
            continue
        if any(iou_hesapla(aday, tahmin) > KONTROL_TAHMIN_IOU for tahmin in tum_tahminler):
            continue
        return aday
    return None


def kirpim_geometrisi(kutu: Kutu, genislik: int, yukseklik: int) -> dict:
    """Siki ve baglam kirpimlarinin piksel koordinatlari."""
    g, y = kutu.genislik, kutu.yukseklik
    pay_x = max(g * SIKI_PAY_ORANI, (SIKI_ASGARI_KENAR - g) / 2, 0)
    pay_y = max(y * SIKI_PAY_ORANI, (SIKI_ASGARI_KENAR - y) / 2, 0)
    siki = _sinirla(kutu.x1 - pay_x, kutu.y1 - pay_y, kutu.x2 + pay_x, kutu.y2 + pay_y,
                    genislik, yukseklik)

    kenar = max(BAGLAM_KATSAYI * max(g, y), BAGLAM_ASGARI_KENAR)
    kenar = min(kenar, genislik, yukseklik)
    mx, my = (kutu.x1 + kutu.x2) / 2, (kutu.y1 + kutu.y2) / 2
    bx1, by1 = mx - kenar / 2, my - kenar / 2
    # Sinirdan tasarsa KAYDIRILIR, kirpilmaz: alan korunsun.
    kaydirma_x = min(0.0, bx1) + max(0.0, bx1 + kenar - genislik)
    kaydirma_y = min(0.0, by1) + max(0.0, by1 + kenar - yukseklik)
    bx1 -= kaydirma_x
    by1 -= kaydirma_y
    baglam = _sinirla(bx1, by1, bx1 + kenar, by1 + kenar, genislik, yukseklik)
    return {
        "siki": siki, "baglam": baglam,
        "kaydirma_x": sayi_bicimle(-kaydirma_x, 1),
        "kaydirma_y": sayi_bicimle(-kaydirma_y, 1),
    }


def _sinirla(x1, y1, x2, y2, genislik, yukseklik):
    return (max(0, int(math.floor(x1))), max(0, int(math.floor(y1))),
            min(genislik, int(math.ceil(x2))), min(yukseklik, int(math.ceil(y2))))


# --- Ornekleme ----------------------------------------------------------------

def katmanli_sec(rastgele, fp_listesi, hedef, taban):
    """Kaynak bazinda katmanli ornekleme; secilme olasiliklarini da dondurur.

    FP sayisi tabandan az olan kaynagin TAMAMI alinir; kalan kontenjan diger
    kaynaklardan buyukten kucuge dagitilir. Amac kucuk kaynagin ornekte
    kaybolmamasi -- kaynak sorusu ancak boyle cevaplanabilir.
    """
    kaynaga_gore = defaultdict(list)
    for kayit in fp_listesi:
        kaynaga_gore[kayit["kaynak_onek"]].append(kayit)

    kucukler = {k: v for k, v in kaynaga_gore.items() if len(v) <= taban}
    buyukler = {k: v for k, v in kaynaga_gore.items() if len(v) > taban}

    secilen, olasilik = [], {}
    for kaynak, kayitlar in sorted(kucukler.items()):
        secilen.extend(kayitlar)
        olasilik[kaynak] = 1.0

    kalan = max(0, hedef - len(secilen))
    toplam_buyuk = sum(len(v) for v in buyukler.values())
    for kaynak, kayitlar in sorted(buyukler.items()):
        pay = kalan if len(buyukler) == 1 else round(kalan * len(kayitlar) / toplam_buyuk)
        pay = min(pay, len(kayitlar))
        ornek = rastgele.sample(sorted(kayitlar, key=lambda k: k["aday_kimligi"]), pay)
        secilen.extend(ornek)
        olasilik[kaynak] = pay / len(kayitlar) if kayitlar else 0.0
    return secilen, olasilik


def main():
    arg = argumanlari_al()
    rastgele = random.Random(TOHUM)

    print("Gercek kutular okunuyor...", flush=True)
    gercekler = gercekleri_oku(arg.veri, arg.bolum)
    print(f"  {len(gercekler)} goruntu, "
          f"{sum(len(v[0]) for v in gercekler.values())} gercek kutu")

    modeller = {}
    for etiket, tahmin_yolu, ozet_yolu in (
        ("Taban-512", arg.taban_tahmin, arg.taban_ozet),
        ("Model-512", arg.model_tahmin, arg.model_ozet),
    ):
        tahminler, kosu = tahmin_kaydi_oku(tahmin_yolu)
        modeller[etiket] = {"tahminler": tahminler, "kosu": kosu, "kaynak": tahmin_yolu.name}
        print(f"{etiket}: {sum(len(v) for v in tahminler.values())} tahmin "
              f"({tahmin_yolu.name})")

    # 1) Capraz kontrol
    print("\n=== TP/FP CAPRAZ KONTROLU ===")
    kontroller = []
    for etiket, ozet_yolu in (("Taban-512", arg.taban_ozet), ("Model-512", arg.model_ozet)):
        kontroller += capraz_kontrol(etiket, gercekler, modeller[etiket]["tahminler"], ozet_yolu)
    for k in kontroller:
        print("  " + " ".join(f"{a}={b}" for a, b in k.items()))
    if any(k.get("durum") not in ("uyustu", "yuvarlama siniri ile aciklandi")
           for k in kontroller):
        raise SystemExit("Capraz kontrol basarisiz: tahmin kaydi olculmus ozetle uyusmuyor.")

    # 2) Calisma noktalari
    taban_ozet = esik_ozeti(gercekler, modeller["Taban-512"]["tahminler"], TABAN_CALISMA_ESIGI)
    butce = taban_ozet["fp_goruntu_basina"]
    model_esik, model_ozet, _egri = butceye_en_yakin_esik(
        gercekler, modeller["Model-512"]["tahminler"], butce)
    print(f"\n=== CALISMA NOKTALARI (esit FP butcesi) ===")
    print(f"  Taban-512 conf={TABAN_CALISMA_ESIGI}  FP={taban_ozet['fp']}  "
          f"FP/gor={taban_ozet['fp_goruntu_basina']:.4f}  recall={taban_ozet['recall']:.4f}")
    print(f"  Model-512 conf={model_esik:.2f}  FP={model_ozet['fp']}  "
          f"FP/gor={model_ozet['fp_goruntu_basina']:.4f}  recall={model_ozet['recall']:.4f}")
    modeller["Taban-512"]["esik"] = TABAN_CALISMA_ESIGI
    modeller["Model-512"]["esik"] = model_esik

    # 3) Aday tablosu: calisma noktasindaki TUM tahminler
    adaylar = []
    fp_havuzu = {}
    for etiket, bilgi in modeller.items():
        isaretli = esikte_isaretle(gercekler, bilgi["tahminler"], bilgi["esik"])
        kisa = "taban" if etiket.startswith("Taban") else "model"
        sayac = 0
        fp_havuzu[etiket] = []
        for ad in sorted(gercekler):
            secilen, harita = isaretli[ad]
            # Ortusen FP elemesi: yuksek skorlu kalir.
            fp_indeksleri = [i for i in range(len(secilen)) if i not in harita]
            elenen = set()
            for i, sol in enumerate(fp_indeksleri):
                if sol in elenen:
                    continue
                for sag in fp_indeksleri[i + 1:]:
                    if sag in elenen:
                        continue
                    if iou_hesapla(secilen[sol], secilen[sag]) > ORTUSEN_FP_IOU:
                        elenen.add(sag)
            for idx, kutu in enumerate(secilen):
                sayac += 1
                gercek_idx, iou_degeri = harita.get(idx, (None, None))
                durum = "TP" if gercek_idx is not None else "FP"
                # FP icin de gercek kutulara en yakin IoU kaydedilir: "hic
                # degmemis" ile "az kalmis" FP ayirt edilebilsin.
                en_iyi_iou = max((iou_hesapla(kutu, g) for g in gercekler[ad][0]),
                                 default=0.0)
                kayit = {
                    "aday_kimligi": f"{kisa}_{sayac:05d}",
                    "model": etiket,
                    "goruntu_adi": ad,
                    "kaynak_onek": onek_cikar(ad),
                    "skor": sayi_bicimle(kutu.skor, 4),
                    "x1": sayi_bicimle(kutu.x1, 1), "y1": sayi_bicimle(kutu.y1, 1),
                    "x2": sayi_bicimle(kutu.x2, 1), "y2": sayi_bicimle(kutu.y2, 1),
                    "kutu_genislik": sayi_bicimle(kutu.genislik, 1),
                    "kutu_yukseklik": sayi_bicimle(kutu.yukseklik, 1),
                    "en_iyi_gt_iou": sayi_bicimle(en_iyi_iou, 4),
                    "eslesen_gt_iou": sayi_bicimle(iou_degeri, 4) if iou_degeri is not None else "",
                    "tp_fp": durum,
                    "calisma_esigi": sayi_bicimle(bilgi["esik"], 2),
                    "fp_butcesi": sayi_bicimle(butce, 4),
                    "dislama_gerekcesi": "ortusen_fp" if idx in elenen else "",
                    "kor_kimlik": "",
                    "_kutu": kutu,
                }
                adaylar.append(kayit)
                if durum == "FP" and idx not in elenen:
                    fp_havuzu[etiket].append(kayit)
        print(f"  {etiket}: {len(fp_havuzu[etiket])} elenmemis FP "
              f"({sum(1 for a in adaylar if a['model']==etiket and a['tp_fp']=='FP')} ham FP)")

    # 4) Ornekleme + kontrol bolgeleri
    print("\n=== ORNEKLEME ===")
    esler = []
    for etiket in ("Taban-512", "Model-512"):
        secilen, olasilik = katmanli_sec(rastgele, fp_havuzu[etiket],
                                         MODEL_BASINA_HEDEF, KATMAN_TABANI)
        print(f"  {etiket}: {len(secilen)} FP secildi; "
              + ", ".join(f"{k}={o:.3f}" for k, o in sorted(olasilik.items())))
        tum_tahmin = {ad: modeller[etiket]["tahminler"].get(ad, []) for ad in gercekler}
        for kayit in sorted(secilen, key=lambda k: k["aday_kimligi"]):
            ad = kayit["goruntu_adi"]
            gercek_kutular, gen, yuk = gercekler[ad]
            secilen_tahmin = [k for k in tum_tahmin[ad] if k.skor >= modeller[etiket]["esik"]]
            kontrol = kontrol_bolgesi_bul(rastgele, kayit["_kutu"], gercek_kutular,
                                          secilen_tahmin, gen, yuk)
            if kontrol is None:
                kayit["dislama_gerekcesi"] = "kontrol_bulunamadi"
                continue
            kayit["katman"] = f"{etiket}/{kayit['kaynak_onek']}"
            kayit["katman_secilme_olasiligi"] = sayi_bicimle(olasilik[kayit["kaynak_onek"]], 4)
            esler.append((kayit, kontrol, gen, yuk))

    # 5) Kor kimlikler
    print(f"\n=== KORLEME === ({len(esler)} cift, {len(esler)*2} aday)")
    kalemler = []
    for kayit, kontrol, gen, yuk in esler:
        for tur, kutu in (("fp", kayit["_kutu"]), ("kontrol", kontrol)):
            kalemler.append({"kayit": kayit, "tur": tur, "kutu": kutu,
                             "genislik": gen, "yukseklik": yuk})
    rastgele.shuffle(kalemler)

    esten_kimlige = defaultdict(dict)
    for sira, kalem in enumerate(kalemler, start=1):
        kalem["kor_kimlik"] = f"a{sira:04d}"
        esten_kimlige[kalem["kayit"]["aday_kimligi"]][kalem["tur"]] = kalem["kor_kimlik"]

    # Kalite (yeniden-test) ornegi: etiketlerden BAGIMSIZ, manifestten sabit
    # tohumla secilir; boylece tek oturumda ikinci tur olarak etiketlenebilir.
    kalite_rastgele = random.Random(TOHUM + 1)
    kalite_sayisi = max(1, round(len(kalemler) * KALITE_ORANI))
    kalite_kimlikleri = set(kalite_rastgele.sample(
        sorted(k["kor_kimlik"] for k in kalemler), kalite_sayisi))
    print(f"  kalite ornegi: {kalite_sayisi} aday (%{KALITE_ORANI*100:.0f})")

    kosu = kosu_bilgisi(
        protokol="reports/hafta7_fp_protokolu.md",
        bolum=arg.bolum,
        goruntu_sayisi=len(gercekler),
        taban_tahmin_kaynagi=arg.taban_tahmin.name,
        model_tahmin_kaynagi=arg.model_tahmin.name,
        taban_calisma_esigi=TABAN_CALISMA_ESIGI,
        model_calisma_esigi=sayi_bicimle(model_esik, 2),
        fp_butcesi=sayi_bicimle(butce, 4),
        eslestirme_iou=ESLESTIRME_IOU,
        ortusen_fp_iou=ORTUSEN_FP_IOU,
        kontrol_tahmin_iou=KONTROL_TAHMIN_IOU,
        baglam_katsayi=BAGLAM_KATSAYI,
        baglam_asgari_kenar=BAGLAM_ASGARI_KENAR,
        model_basina_hedef=MODEL_BASINA_HEDEF,
        katman_tabani=KATMAN_TABANI,
        tohum=TOHUM,
        kapsam_notu=("Esikler, katsayilar ve ornek buyuklukleri KARARDIR; "
                     "olcumden turetilmedi. Ayrinti protokol dosyasinda."),
    )

    # --- aday tablosu
    aday_satirlari = []
    for kayit in adaylar:
        kimlikler = esten_kimlige.get(kayit["aday_kimligi"], {})
        satir = {k: v for k, v in kayit.items() if not k.startswith("_")}
        satir["kor_kimlik"] = kimlikler.get("fp", "")
        satir["kontrol_kor_kimlik"] = kimlikler.get("kontrol", "")
        satir["ornege_alindi"] = "evet" if kimlikler else "hayir"
        satir.setdefault("katman", "")
        satir.setdefault("katman_secilme_olasiligi", "")
        aday_satirlari.append(satir)
    csv_yaz(arg.aday_cikti, aday_satirlari, kosu)
    print(f"\nAday tablosu: {arg.aday_cikti} ({len(aday_satirlari)} satir)")

    # --- manifest (KOR: model, tur, skor, kaynak, dosya adi YOK)
    manifest, anahtar = [], []
    for kalem in sorted(kalemler, key=lambda k: k["kor_kimlik"]):
        kayit, kutu = kalem["kayit"], kalem["kutu"]
        geo = kirpim_geometrisi(kutu, kalem["genislik"], kalem["yukseklik"])
        sx1, sy1, sx2, sy2 = geo["siki"]
        bx1, by1, bx2, by2 = geo["baglam"]
        kimlik = kalem["kor_kimlik"]
        manifest.append({
            "kor_kimlik": kimlik,
            "siki_kirpim": f"{kimlik}_siki.jpg",
            "baglam_kirpim": f"{kimlik}_baglam.jpg",
            "siki_genislik": sx2 - sx1, "siki_yukseklik": sy2 - sy1,
            "baglam_genislik": bx2 - bx1, "baglam_yukseklik": by2 - by1,
            "baglam_kaydirma_x": geo["kaydirma_x"], "baglam_kaydirma_y": geo["kaydirma_y"],
            "tur": "kalite" if kimlik in kalite_kimlikleri else "ana",
        })
        anahtar.append({
            "kor_kimlik": kimlik,
            "aday_turu": kalem["tur"],
            "es_kor_kimlik": esten_kimlige[kayit["aday_kimligi"]][
                "kontrol" if kalem["tur"] == "fp" else "fp"],
            "model": kayit["model"],
            "aday_kimligi": kayit["aday_kimligi"],
            "goruntu_adi": kayit["goruntu_adi"],
            "kaynak_onek": kayit["kaynak_onek"],
            "skor": kayit["skor"] if kalem["tur"] == "fp" else "",
            "x1": sayi_bicimle(kutu.x1, 1), "y1": sayi_bicimle(kutu.y1, 1),
            "x2": sayi_bicimle(kutu.x2, 1), "y2": sayi_bicimle(kutu.y2, 1),
            "siki_x1": sx1, "siki_y1": sy1, "siki_x2": sx2, "siki_y2": sy2,
            "baglam_x1": bx1, "baglam_y1": by1, "baglam_x2": bx2, "baglam_y2": by2,
            "katman": kayit["katman"],
            "katman_secilme_olasiligi": kayit["katman_secilme_olasiligi"],
            "calisma_esigi": kayit["calisma_esigi"],
            "fp_butcesi": kayit["fp_butcesi"],
            "kalite_ornegi": "evet" if kimlik in kalite_kimlikleri else "hayir",
        })
    csv_yaz(arg.manifest_cikti, manifest, kosu)
    csv_yaz(arg.anahtar_cikti, anahtar, kosu)
    print(f"Manifest     : {arg.manifest_cikti} ({len(manifest)} aday)")
    print(f"Korleme anaht: {arg.anahtar_cikti}")

    # --- sizinti denetimi
    YASAK = ("Taban", "Model", "ZRI", "VRD", ".rf.", "jpg.rf")
    sizdiran = [s for s in manifest
                if any(yasak in str(deger)
                       for deger in s.values() for yasak in YASAK)]
    if sizdiran:
        raise SystemExit(f"Manifest sizdiriyor: {sizdiran[:2]}")
    print("Sizinti denetimi: manifest'te model/kaynak/dosya adi yok.")


if __name__ == "__main__":
    main()
