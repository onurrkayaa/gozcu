#!/usr/bin/env python3
"""Kor etiketleri korleme anahtariyla birlestirip protokoldeki analizleri uretir.

Korleme anahtari YALNIZCA burada acilir; etiketleme araci bu dosyayi hic
gormez.

Birincil analiz eslestirilmis bir karsilastirmadir: her yanlis pozitif bolge,
AYNI GORUNTUDEN secilmis kendi kontrol bolgesiyle karsilastirilir. Iki bagimsiz
oran testi burada gecersizdir, cunku ciftin iki uyesi ayni goruntuden gelir.
Guven araligi GORUNTU duzeyinde kume bootstrap ile uretilir: ayni goruntuden
gelen ciftler birlikte yeniden orneklenir, aksi halde aralik yapay olarak
daralir.

Butun esikler, agirliklar ve karar kurallari reports/hafta7_fp_protokolu.md
icinde, sonuclar gorulmeden once sabitlendi.
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ortak import RAPOR_KOK, csv_yaz, kosu_bilgisi, sayi_bicimle  # noqa: E402

TOHUM = 20260913
BOOTSTRAP = 10000
ASGARI_ANA_BULGU = 100
AZ_ORNEK_SINIRI = 50
YENIDEN_TEST_ESIGI = 0.80
PRATIK_FARK_SINIRI = 0.05


# --- Saf istatistik -----------------------------------------------------------

def mcnemar_tam(b: int, c: int) -> float:
    """Uyumsuz ciftler uzerinde iki yonlu tam binom testi.

    b: FP'de var / kontrolde yok olan cift sayisi.
    c: FP'de yok / kontrolde var olan cift sayisi.
    Uyumlu ciftler (ikisi de ayni) teste HIC girmez; eslestirilmis tasarimda
    bilgi tasiyan yalnizca uyumsuz ciftlerdir.
    """
    n = b + c
    if n == 0:
        return 1.0
    kucuk = min(b, c)
    kuyruk = sum(math.comb(n, k) for k in range(kucuk + 1)) * (0.5 ** n)
    return min(1.0, 2.0 * kuyruk)


def agirlikli_fark(ciftler) -> float:
    """Agirlikli p(FP) - p(kontrol).

    Ornekleme katmanli oldugu icin her cift, katmaninin secilme olasiliginin
    tersiyle agirliklandirilir; aksi halde tamami alinan kucuk kaynak birlesik
    oranda hak ettiginden fazla yer tutar.
    """
    toplam_agirlik = sum(c["agirlik"] for c in ciftler)
    if toplam_agirlik == 0:
        return 0.0
    return sum(c["agirlik"] * (c["fp"] - c["kontrol"]) for c in ciftler) / toplam_agirlik


def kume_bootstrap(ciftler, olcu, yineleme=BOOTSTRAP, tohum=TOHUM):
    """Goruntu duzeyinde kume bootstrap; (alt, ust) %95 araligi dondurur."""
    if not ciftler:
        return (float("nan"), float("nan"))
    goruntuye_gore = defaultdict(list)
    for cift in ciftler:
        goruntuye_gore[cift["goruntu"]].append(cift)
    goruntuler = sorted(goruntuye_gore)
    rastgele = random.Random(tohum)
    dagilim = []
    for _ in range(yineleme):
        secilen = []
        for _ in range(len(goruntuler)):
            secilen.extend(goruntuye_gore[goruntuler[rastgele.randrange(len(goruntuler))]])
        dagilim.append(olcu(secilen))
    dagilim.sort()
    alt = dagilim[int(0.025 * (len(dagilim) - 1))]
    ust = dagilim[int(round(0.975 * (len(dagilim) - 1)))]
    return (alt, ust)


def kanit_etiketi(gecerli_cift, alt, ust, duyarliliklar, yeniden_test, kaynak_yonleri):
    """Protokolde onceden baglanmis karar kurali. Sonuca bakip degistirilmez."""
    if gecerli_cift < ASGARI_ANA_BULGU:
        return "ILGINC AMA KANITLANMAMIS", "gecerli cift sayisi 100'un altinda"
    if not math.isnan(alt) and alt > 0:
        ayni_yon = all(d > 0 for d in duyarliliklar)
        kaynak_ters = any(y < 0 for y in kaynak_yonleri)
        if ayni_yon and yeniden_test >= YENIDEN_TEST_ESIGI and not kaynak_ters:
            return "BULGU", "aralik sifiri disliyor, duyarliliklar ayni yonde, yeniden-test yeterli"
        gerekce = []
        if not ayni_yon:
            gerekce.append("duyarlilik analizleri ayrisiyor")
        if yeniden_test < YENIDEN_TEST_ESIGI:
            gerekce.append("yeniden-test uyumu esigin altinda")
        if kaynak_ters:
            gerekce.append("yon en az bir kaynakta tersine donuyor")
        return "ILGINC AMA KANITLANMAMIS", "; ".join(gerekce)
    if not math.isnan(ust) and ust < 0:
        return "CURUTULDU", "aralik sifiri TERS yonde disliyor"
    if not math.isnan(alt) and abs(alt) < PRATIK_FARK_SINIRI and abs(ust) < PRATIK_FARK_SINIRI:
        return "CURUTULDU", "aralik sifiri iceriyor ve iki ucu da +-0,05'ten kucuk"
    return "ILGINC AMA KANITLANMAMIS", "aralik sifiri iceriyor"


def uyum_orani(ilk: dict, ikinci: dict, alan: str) -> tuple[int, int]:
    """Ayni kimliklerde iki turun uyusan sayisi ve karsilastirilan sayi."""
    ortak = sorted(set(ilk) & set(ikinci))
    uyusan = sum(1 for k in ortak if ilk[k].get(alan) == ikinci[k].get(alan))
    return uyusan, len(ortak)


# --- Veri ---------------------------------------------------------------------

def csv_oku(yol: Path) -> list[dict]:
    with yol.open(encoding="utf-8") as dosya:
        return list(csv.DictReader(dosya))


def ciftleri_kur(etiketler_ana, anahtar_satirlari, belirsiz_politikasi="disla"):
    """Etiket + anahtar -> analiz ciftleri.

    belirsiz_politikasi: 'disla' (birincil), 'yok' veya 'var' (duyarlilik).
    Dislama CIFT BAZINDADIR: eslestirilmis tasarimda bir uye duserse digeri de
    duser, yoksa karsilastirma eslestirilmis olmaktan cikar.
    """
    ciftler, dislanan = [], Counter()

    for satir in anahtar_satirlari:
        if satir["aday_turu"] != "fp":
            continue
        fp_kimlik = satir["kor_kimlik"]
        kontrol_kimlik = satir["es_kor_kimlik"]
        fp_etiket = etiketler_ana.get(fp_kimlik)
        kontrol_etiket = etiketler_ana.get(kontrol_kimlik)
        if fp_etiket is None or kontrol_etiket is None:
            dislanan["etiketsiz"] += 1
            continue
        if "hayir" in (fp_etiket.get("goruntu_yeterli"), kontrol_etiket.get("goruntu_yeterli")):
            dislanan["goruntu_yetersiz"] += 1
            continue

        degerler = []
        for etiket in (fp_etiket, kontrol_etiket):
            deger = etiket.get("insan_faaliyeti")
            if deger == "belirsiz":
                if belirsiz_politikasi == "disla":
                    degerler = None
                    break
                deger = belirsiz_politikasi
            degerler.append(1 if deger == "var" else 0)
        if degerler is None:
            dislanan["belirsiz"] += 1
            continue

        olasilik = float(satir["katman_secilme_olasiligi"] or 1.0)
        ciftler.append({
            "fp_kor_kimlik": fp_kimlik,
            "kontrol_kor_kimlik": kontrol_kimlik,
            "goruntu": satir["goruntu_adi"],
            "model": satir["model"],
            "kaynak": satir["kaynak_onek"],
            "katman": satir["katman"],
            "agirlik": 1.0 / olasilik if olasilik > 0 else 1.0,
            "fp": degerler[0],
            "kontrol": degerler[1],
            "fp_alt_kategori": fp_etiket.get("alt_kategori", ""),
            "kontrol_alt_kategori": kontrol_etiket.get("alt_kategori", ""),
            "skor": float(satir["skor"]) if satir.get("skor") else None,
        })
    return ciftler, dislanan


def grup_ozeti(ad, ciftler):
    """Bir cift kumesi icin sayimlar, fark, aralik ve test."""
    n = len(ciftler)
    b = sum(1 for c in ciftler if c["fp"] == 1 and c["kontrol"] == 0)
    cc = sum(1 for c in ciftler if c["fp"] == 0 and c["kontrol"] == 1)
    fark = agirlikli_fark(ciftler)
    alt, ust = kume_bootstrap(ciftler, agirlikli_fark)
    toplam_agirlik = sum(c["agirlik"] for c in ciftler) or 1.0
    return {
        "grup": ad,
        "gecerli_cift": n,
        "fp_insan_faaliyeti": sum(c["fp"] for c in ciftler),
        "kontrol_insan_faaliyeti": sum(c["kontrol"] for c in ciftler),
        "fp_orani_agirlikli": sayi_bicimle(
            sum(c["agirlik"] * c["fp"] for c in ciftler) / toplam_agirlik, 4),
        "kontrol_orani_agirlikli": sayi_bicimle(
            sum(c["agirlik"] * c["kontrol"] for c in ciftler) / toplam_agirlik, 4),
        "agirlikli_fark": sayi_bicimle(fark, 4),
        "guven_araligi_alt": sayi_bicimle(alt, 4) if not math.isnan(alt) else "",
        "guven_araligi_ust": sayi_bicimle(ust, 4) if not math.isnan(ust) else "",
        "uyumsuz_fp_lehine": b,
        "uyumsuz_kontrol_lehine": cc,
        "eslestirilmis_odds_orani": sayi_bicimle(b / cc, 4) if cc else "",
        "mcnemar_p": sayi_bicimle(mcnemar_tam(b, cc), 5),
        "goruntu_sayisi": len({c["goruntu"] for c in ciftler}),
        "ornek_bayragi": ("yeterli" if n >= ASGARI_ANA_BULGU
                          else "az ornek" if n >= AZ_ORNEK_SINIRI
                          else "bagimsiz sonuc degil"),
    }


def main():
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--etiketler", type=Path, default=RAPOR_KOK / "hafta7_fp_gorsel_etiketler.csv")
    a.add_argument("--anahtar", type=Path, default=RAPOR_KOK / "hafta7_fp_korleme_anahtari.csv")
    a.add_argument("--manifest", type=Path, default=RAPOR_KOK / "hafta7_fp_etiket_manifesti.csv")
    a.add_argument("--analiz-cikti", type=Path,
                   default=RAPOR_KOK / "hafta7_fp_insan_faaliyeti_analizi.csv")
    a.add_argument("--kaynak-cikti", type=Path, default=RAPOR_KOK / "hafta7_fp_kaynak_kirilimi.csv")
    a.add_argument("--kategori-cikti", type=Path,
                   default=RAPOR_KOK / "hafta7_fp_kategori_kirilimi.csv")
    a.add_argument("--kalite-cikti", type=Path, default=RAPOR_KOK / "hafta7_fp_etiket_kalite.csv")
    arg = a.parse_args()

    etiket_satirlari = csv_oku(arg.etiketler)
    anahtar_satirlari = csv_oku(arg.anahtar)
    manifest = csv_oku(arg.manifest)
    manifest_kimlikleri = {s["kor_kimlik"] for s in manifest}

    ana = {s["kor_kimlik"]: s for s in etiket_satirlari if s.get("mod") == "ana"}
    kalite = {s["kor_kimlik"]: s for s in etiket_satirlari if s.get("mod") == "kalite"}
    disarida = [s for s in etiket_satirlari if s["kor_kimlik"] not in manifest_kimlikleri]
    if disarida:
        raise SystemExit(f"Etiket dosyasinda manifest disi {len(disarida)} kimlik var.")

    # --- Etiket kalitesi (yeniden-test) --------------------------------------
    kalite_satirlari = []
    for alan, ad in (("insan_faaliyeti", "insan faaliyeti (ikili alan)"),
                     ("alt_kategori", "alt kategori"),
                     ("guven", "guven")):
        uyusan, karsilastirilan = uyum_orani(ana, kalite, alan)
        kalite_satirlari.append({
            "olcum": ad, "alan": alan,
            "karsilastirilan_kayit": karsilastirilan, "uyusan": uyusan,
            "uyum_orani": sayi_bicimle(uyusan / karsilastirilan, 4) if karsilastirilan else "",
            "esik": YENIDEN_TEST_ESIGI if alan == "insan_faaliyeti" else "",
            "sonuc": ("gecti" if alan == "insan_faaliyeti" and karsilastirilan
                      and uyusan / karsilastirilan >= YENIDEN_TEST_ESIGI
                      else "kaldi" if alan == "insan_faaliyeti" else "bilgi"),
        })
    tam_uyum, tam_karsilastirilan = 0, 0
    for kimlik in sorted(set(ana) & set(kalite)):
        tam_karsilastirilan += 1
        if all(ana[kimlik].get(x) == kalite[kimlik].get(x)
               for x in ("insan_faaliyeti", "alt_kategori", "guven")):
            tam_uyum += 1
    kalite_satirlari.insert(0, {
        "olcum": "tam uyum (uc alan birden)", "alan": "hepsi",
        "karsilastirilan_kayit": tam_karsilastirilan, "uyusan": tam_uyum,
        "uyum_orani": sayi_bicimle(tam_uyum / tam_karsilastirilan, 4) if tam_karsilastirilan else "",
        "esik": "", "sonuc": "bilgi",
    })
    belirsiz_ana = sum(1 for s in ana.values() if s.get("insan_faaliyeti") == "belirsiz")
    kalite_satirlari.append({
        "olcum": "belirsiz orani (ana tur)", "alan": "insan_faaliyeti",
        "karsilastirilan_kayit": len(ana), "uyusan": belirsiz_ana,
        "uyum_orani": sayi_bicimle(belirsiz_ana / len(ana), 4) if ana else "",
        "esik": "", "sonuc": "bilgi",
    })
    kalite_satirlari.append({
        "olcum": "yeniden inceleme isareti (ana tur)", "alan": "yeniden_incele",
        "karsilastirilan_kayit": len(ana),
        "uyusan": sum(1 for s in ana.values() if s.get("yeniden_incele") == "evet"),
        "uyum_orani": "", "esik": "", "sonuc": "bilgi",
    })
    kalite_satirlari.append({
        "olcum": "goruntu yetersiz (ana tur)", "alan": "goruntu_yeterli",
        "karsilastirilan_kayit": len(ana),
        "uyusan": sum(1 for s in ana.values() if s.get("goruntu_yeterli") == "hayir"),
        "uyum_orani": "", "esik": "", "sonuc": "bilgi",
    })

    ikili_uyum = next(
        (float(s["uyum_orani"]) for s in kalite_satirlari
         if s["alan"] == "insan_faaliyeti" and s["olcum"].startswith("insan faaliyeti")
         and s["uyum_orani"] != ""), 0.0)

    kosu = kosu_bilgisi(
        protokol="reports/hafta7_fp_protokolu.md",
        etiket_kaynagi=arg.etiketler.name,
        anahtar_kaynagi=arg.anahtar.name,
        bootstrap_yineleme=BOOTSTRAP,
        tohum=TOHUM,
        yeniden_test_esigi=YENIDEN_TEST_ESIGI,
        kapsam_notu=("Tek etiketleyici yeniden-test tutarliligi olculdu; "
                     "annotatorlar arasi guvenilirlik DEGILDIR. Nedensellik "
                     "iddiasi kurulmaz."),
    )
    csv_yaz(arg.kalite_cikti, kalite_satirlari, kosu)

    # --- Birincil analiz ------------------------------------------------------
    ciftler, dislanan = ciftleri_kur(ana, anahtar_satirlari, "disla")
    duyarlilik = {}
    for politika in ("yok", "var"):
        d_ciftler, _ = ciftleri_kur(ana, anahtar_satirlari, politika)
        duyarlilik[politika] = agirlikli_fark(d_ciftler)

    satirlar = [grup_ozeti("TUMU (birincil)", ciftler)]
    for model in sorted({c["model"] for c in ciftler}):
        satirlar.append(grup_ozeti(model, [c for c in ciftler if c["model"] == model]))

    kaynak_yonleri = []
    for kaynak in sorted({c["kaynak"] for c in ciftler}):
        alt_ciftler = [c for c in ciftler if c["kaynak"] == kaynak]
        if len(alt_ciftler) >= AZ_ORNEK_SINIRI:
            kaynak_yonleri.append(agirlikli_fark(alt_ciftler))

    etiket, gerekce = kanit_etiketi(
        len(ciftler),
        float(satirlar[0]["guven_araligi_alt"] or "nan"),
        float(satirlar[0]["guven_araligi_ust"] or "nan"),
        list(duyarlilik.values()), ikili_uyum, kaynak_yonleri)

    for politika, deger in duyarlilik.items():
        satirlar.append({
            "grup": f"duyarlilik: belirsiz -> {politika}",
            "gecerli_cift": "", "agirlikli_fark": sayi_bicimle(deger, 4),
            "ornek_bayragi": "duyarlilik",
        })
    for gerekce_adi, sayi in sorted(dislanan.items()):
        satirlar.append({"grup": f"dislanan cift: {gerekce_adi}", "gecerli_cift": sayi,
                         "ornek_bayragi": "dislama"})
    satirlar.append({"grup": "KANIT ETIKETI", "ornek_bayragi": etiket,
                     "mcnemar_p": "", "agirlikli_fark": "", "gecerli_cift": "",
                     "guven_araligi_alt": gerekce})
    csv_yaz(arg.analiz_cikti, satirlar, kosu)

    # --- Kaynak kirilimi ------------------------------------------------------
    kaynak_satirlari = []
    for ad, secim in [("TUMU", lambda c: True),
                      ("ZRI", lambda c: c["kaynak"] == "ZRI"),
                      ("ZRI_HARIC", lambda c: c["kaynak"] != "ZRI")]:
        alt_ciftler = [c for c in ciftler if secim(c)]
        if alt_ciftler:
            kaynak_satirlari.append({**grup_ozeti(ad, alt_ciftler), "kirilim": "kaynak"})
    for kaynak in sorted({c["kaynak"] for c in ciftler}):
        for model in sorted({c["model"] for c in ciftler}):
            alt_ciftler = [c for c in ciftler if c["kaynak"] == kaynak and c["model"] == model]
            if alt_ciftler:
                kaynak_satirlari.append(
                    {**grup_ozeti(f"{kaynak} / {model}", alt_ciftler), "kirilim": "kaynak x model"})
    csv_yaz(arg.kaynak_cikti, kaynak_satirlari, kosu)

    # --- Kategori kirilimi ----------------------------------------------------
    kategori_satirlari = []
    sayimlar = defaultdict(Counter)
    for cift in ciftler:
        sayimlar[(cift["model"], "fp")][cift["fp_alt_kategori"]] += 1
        sayimlar[(cift["model"], "kontrol")][cift["kontrol_alt_kategori"]] += 1
    for (model, tur), sayim in sorted(sayimlar.items()):
        toplam = sum(sayim.values())
        for kategori, adet in sorted(sayim.items(), key=lambda x: (-x[1], x[0])):
            kategori_satirlari.append({
                "model": model, "bolge_turu": tur, "alt_kategori": kategori,
                "adet": adet, "grup_toplami": toplam,
                "oran": sayi_bicimle(adet / toplam, 4) if toplam else "",
                "ornek_bayragi": ("yeterli" if adet >= ASGARI_ANA_BULGU
                                  else "az ornek" if adet >= AZ_ORNEK_SINIRI
                                  else "bagimsiz sonuc degil"),
            })
    # Arac kategorisi ayrica: Hafta 4'teki araba gozleminin karsiligi.
    arac_toplam = sum(s["adet"] for s in kategori_satirlari
                      if s["alt_kategori"] == "arac" and s["bolge_turu"] == "fp")
    kategori_satirlari.append({
        "model": "TUMU", "bolge_turu": "fp", "alt_kategori": "arac (ozet)",
        "adet": arac_toplam, "grup_toplami": len(ciftler),
        "oran": sayi_bicimle(arac_toplam / len(ciftler), 4) if ciftler else "",
        "ornek_bayragi": ("yeterli" if arac_toplam >= ASGARI_ANA_BULGU
                          else "az ornek" if arac_toplam >= AZ_ORNEK_SINIRI
                          else "bagimsiz sonuc degil; yalnizca ornek olarak kalir"),
    })
    # Aciklayici: skor ile insan faaliyeti iliskisi (protokolde onceden aciklayici).
    skorlu = [c for c in ciftler if c["skor"] is not None]
    if skorlu:
        for etiket_degeri in (1, 0):
            secilen = [c["skor"] for c in skorlu if c["fp"] == etiket_degeri]
            if secilen:
                kategori_satirlari.append({
                    "model": "TUMU", "bolge_turu": "aciklayici_skor",
                    "alt_kategori": "insan faaliyeti var" if etiket_degeri else "insan faaliyeti yok",
                    "adet": len(secilen), "grup_toplami": len(skorlu),
                    "oran": sayi_bicimle(sum(secilen) / len(secilen), 4),
                    "ornek_bayragi": "ACIKLAYICI: protokolde bulgu etiketi verilmez",
                })
    csv_yaz(arg.kategori_cikti, kategori_satirlari, kosu)

    # --- Ozet -----------------------------------------------------------------
    print("=== ETIKET KALITESI ===")
    for s in kalite_satirlari:
        print(f"  {s['olcum']:34} {s['uyusan']}/{s['karsilastirilan_kayit']} "
              f"oran={s['uyum_orani']} {s['sonuc']}")
    print("\n=== BIRINCIL ANALIZ ===")
    ilk = satirlar[0]
    print(f"  gecerli cift          : {ilk['gecerli_cift']} "
          f"({ilk['goruntu_sayisi']} goruntu)")
    print(f"  FP insan faaliyeti    : {ilk['fp_orani_agirlikli']}")
    print(f"  kontrol               : {ilk['kontrol_orani_agirlikli']}")
    print(f"  agirlikli fark        : {ilk['agirlikli_fark']} "
          f"[{ilk['guven_araligi_alt']}, {ilk['guven_araligi_ust']}]")
    print(f"  McNemar p             : {ilk['mcnemar_p']} "
          f"(b={ilk['uyumsuz_fp_lehine']}, c={ilk['uyumsuz_kontrol_lehine']})")
    print(f"  KANIT ETIKETI         : {etiket} -- {gerekce}")
    print("\nYazilan dosyalar:")
    for yol in (arg.kalite_cikti, arg.analiz_cikti, arg.kaynak_cikti, arg.kategori_cikti):
        print(f"  {yol}")


if __name__ == "__main__":
    main()
