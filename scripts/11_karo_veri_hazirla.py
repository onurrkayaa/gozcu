"""4000x3000 goruntuleri ortusmeli karolara keser ve YOLO formatinda egitim
kumesi uretir.

Neden karolama: medyan hedef 60x59 piksel. 4000x3000 goruntu modelin 640 px'lik
girisine kuculdugunde bu hedef ~10 piksele iner ve ogrenilecek bir sey kalmaz.

Karo/ortusme eslesmesi (VARSAYILAN_ORTUSME):
    karo 512 -> ortusme 0,20 (102 px)
    karo 320 -> ortusme 0,25 ( 80 px)
    karo 256 -> ortusme 0,30 ( 76 px)
SEBEBI: ortusme piksel cinsinden medyan kutudan (60 px) BUYUK olmali. Kucuk
olsaydi iki karonun arasina dusen bir hedef hicbir karoda butun kalmaz, %60
gorunurluk kurali onu ikisinden de atar ve hedef egitim verisinden tamamen
kaybolurdu. Ortusme buyuk oldugu icin tipik bir hedef en az bir karoda butun
kalir; bu varsayim kod tarafindan ayrica OLCULUR (bkz. butun_kalmayan sayimi).

TEST BOLUMU KAROLANMAZ. Test olcumu tam goruntu uzerinde SAHI ile yapilir ve
egitim protokolunden bagimsiz kalmalidir.
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIZIN = Path(__file__).resolve().parent
PROJE_KOK = SCRIPT_DIZIN.parent
sys.path.insert(0, str(SCRIPT_DIZIN))
sys.path.insert(0, str(PROJE_KOK / "backend"))

from ortak import (  # noqa: E402
    RAPOR_KOK,
    VERI_KOK,
    bolum_yolu,
    csv_yaz,
    etiket_yolu,
    goruntuleri_listele,
    kosu_bilgisi,
    sayi_bicimle,
    tablo_bas,
    yolo_etiket_oku,
)

# Karolama mantigi backend'de yasar ve TEK kopyasi vardir; burada yeniden
# yazilmaz. Ayni mantigin iki yerde olmasi, egitim verisiyle cikarim
# karolamasinin sessizce birbirinden kaymasi demektir.
from core.tiling import karolari_hesapla  # noqa: E402

VARSAYILAN_ORTUSME = {512: 0.20, 320: 0.25, 256: 0.30}
VARSAYILAN_KARO = 320
MEDYAN_KUTU_PX = 60  # Hafta 0 olcumu: medyan kutu 60x59 px.

# Negatif ornekleme tohumu. Sabit tutulur ki ayni argumanlar her calistirmada
# ayni egitim kumesini uretsin.
TOHUM = 0

# Kaynak bolum adi -> YOLO dizin adi. Ultralytics 'val' bekler.
BOLUM_ESLESMESI = {"train": "train", "valid": "val"}

# Alt kume uzerinde uretilen veri kumesi gercek egitim kumesi degildir; adina
# bu onek gelir ki karismasin.
DENEME_ONEKI = "DENEME_"

ILERLEME_ARALIGI = 200


# --- Saf geometri -------------------------------------------------------------


def ortusme_piksel(karo_boyu: int, ortusme_orani: float) -> int:
    """Ortusmenin piksel karsiligini dondurur.

    Formulu kopyalamak yerine karolari_hesapla'nin urettigi ilk iki karo
    arasindaki adimdan geri hesapliyoruz. Boylece bu sayi, gercek karolamanin
    kullandigi degerden hicbir kosulda ayrilamaz.
    """
    # En az iki karo cikacak kadar genis, tek satir olacak kadar alcak bir kenar.
    karolar = karolari_hesapla(karo_boyu * 4, karo_boyu, karo_boyu, ortusme_orani)
    adim = karolar[1][2] - karolar[0][2]
    return karo_boyu - adim


def gorunur_oran(kutu: tuple, karo: tuple) -> float:
    """Kutunun alaninin ne kadarinin karo icinde kaldigini [0,1] araliginda dondurur."""
    kx1, ky1, kx2, ky2 = kutu
    tx1, ty1, tx2, ty2 = karo

    g = min(kx2, tx2) - max(kx1, tx1)
    y = min(ky2, ty2) - max(ky1, ty1)
    if g <= 0 or y <= 0:
        return 0.0

    alan = (kx2 - kx1) * (ky2 - ky1)
    if alan <= 0:
        return 0.0
    return (g * y) / alan


def kutuyu_karoya_tasi(kutu: tuple, karo: tuple, min_gorunur: float):
    """Kutuyu karo duzlemine tasir ve YOLO (xmerkez, ymerkez, g, y) olarak normalize eder.

    Kutunun karo icinde kalan alani orijinalin min_gorunur oranindan azsa None
    doner: etiket O KARODA atlanir. Kutu silinmis olmaz -- baska bir karoda
    butun kalabilir.
    """
    if gorunur_oran(kutu, karo) < min_gorunur:
        return None

    kx1, ky1, kx2, ky2 = kutu
    tx1, ty1, tx2, ty2 = karo
    karo_g = tx2 - tx1
    karo_y = ty2 - ty1

    # Karo sinirina kirp, sonra karo kosesini cikararak yerel koordinata gec.
    x1 = max(kx1, tx1) - tx1
    y1 = max(ky1, ty1) - ty1
    x2 = min(kx2, tx2) - tx1
    y2 = min(ky2, ty2) - ty1

    return (
        (x1 + x2) / 2 / karo_g,
        (y1 + y2) / 2 / karo_y,
        (x2 - x1) / karo_g,
        (y2 - y1) / karo_y,
    )


def karo_kategorisi(kutular: list, karo: tuple, min_gorunur: float) -> str:
    """Karoyu pozitif / belirsiz / negatif olarak siniflar.

    pozitif : en az bir etiket gorunurluk kuralini gecti.
    belirsiz: icinde hedef var ama hicbiri kurali gecemedi. Bu karo hicbir yere
              yazilmaz. Negatif havuzuna atilirsa modele "yarim insan = arka
              plan" ogretilir ki aradigimiz seyin tam tersidir.
    negatif : hicbir hedefle kesismiyor; gercek arka plandir.
    """
    kesisen = False
    for kutu in kutular:
        oran = gorunur_oran(kutu, karo)
        if oran >= min_gorunur:
            return "pozitif"
        if oran > 0:
            kesisen = True
    return "belirsiz" if kesisen else "negatif"


def negatif_ornekle(adaylar: list, sayi: int, tohum: int) -> list:
    """Negatif aday karolardan sabit tohumla rastgele ornek secer.

    Aday sayisi istenenden azsa hepsi dondurulur; eksik negatif bir hata degil,
    sadece daha az arka plan ornegidir.
    """
    if sayi >= len(adaylar):
        return list(adaylar)
    return random.Random(tohum).sample(list(adaylar), sayi)


# --- Komut satiri -------------------------------------------------------------


def argumanlari_coz() -> argparse.Namespace:
    ayrastirici = argparse.ArgumentParser(
        description=(
            "train ve valid bolumlerini ortusmeli karolara keserek YOLO egitim "
            "kumesi uretir. Test bolumu karolanmaz."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Veri kumesi kok klasoru")
    ayrastirici.add_argument("--karo", type=int, default=VARSAYILAN_KARO, help="Karo kenar uzunlugu, piksel")
    ayrastirici.add_argument(
        "--ortusme", type=float, default=None,
        help="Ortusme orani. Verilmezse karo boyuna gore varsayilan tablodan alinir.",
    )
    ayrastirici.add_argument("--negatif", type=int, default=3, help="Pozitif karo basina kac negatif karo ornekle")
    ayrastirici.add_argument("--min-gorunur", type=float, default=0.6, help="Kenar kutu gorunurluk esigi")
    ayrastirici.add_argument("--cikti", type=Path, default=None, help="Cikti dizini (varsayilan: data/karo_<karo>)")
    ayrastirici.add_argument(
        "--limit", type=int, default=0,
        help=(
            "Deneme kosusu icin bolum basina en fazla kac goruntu islensin (0 = hepsi). "
            f"Sifirdan buyukse cikti dizini ve manifest {DENEME_ONEKI} onekiyle yazilir; "
            "alt kume uzerinde uretilen veri kumesi gercek egitim kumesi degildir."
        ),
    )
    return ayrastirici.parse_args()


def ortusmeyi_sec(karo: int, verilen: float | None) -> float:
    """Ortusme oranini belirler ve medyan kutu kuralini dogrular."""
    if verilen is not None:
        return verilen
    if karo not in VARSAYILAN_ORTUSME:
        raise SystemExit(
            f"Karo {karo} icin varsayilan ortusme tanimli degil "
            f"(tanimli olanlar: {sorted(VARSAYILAN_ORTUSME)}). --ortusme ile acikca verin."
        )
    return VARSAYILAN_ORTUSME[karo]


# --- Karolama gecisleri -------------------------------------------------------


def bolumu_planla(bolum: str, veri_kok: Path, karo: int, ortusme: float,
                  min_gorunur: float, limit: int) -> dict:
    """Piksel okumadan once tum karolari siniflar ve etiketleri hesaplar.

    Iki gecisli calisiyoruz: burada sadece geometri var (goruntu basligindan
    olcu, etiket dosyasindan kutular). Hangi karolarin yazilacagi belli olduktan
    sonra ikinci gecis her goruntuyu BIR KEZ acar. Tek gecisle yapsaydik,
    orneklenen negatifler icin 4000x3000 goruntuleri yeniden acmak gerekirdi.
    """
    from PIL import Image

    goruntu_dizin, etiket_dizin = bolum_yolu(bolum, veri_kok)
    goruntuler = goruntuleri_listele(goruntu_dizin, limit or None)

    pozitifler: list[tuple] = []       # (goruntu, satir, sutun, karo, etiketler)
    negatif_adaylar: list[tuple] = []  # (goruntu, satir, sutun, karo)
    belirsizler: list[tuple] = []      # (goruntu, satir, sutun, karo)
    atlanan_etiket = 0
    butun_kalmayan: list[dict] = []

    for sira, yol in enumerate(goruntuler, start=1):
        with Image.open(yol) as gorsel:
            genislik, yukseklik = gorsel.size
        kutu_nesneleri = yolo_etiket_oku(etiket_yolu(yol, etiket_dizin), genislik, yukseklik)
        kutular = [(k.x1, k.y1, k.x2, k.y2) for k in kutu_nesneleri]

        # Her hedef en az bir karoda butun kaldi mi? Kalmadiysa egitim
        # verisinden tamamen kaybolmus demektir.
        yerlesen = set()

        for satir, sutun, x1, y1, x2, y2 in karolari_hesapla(genislik, yukseklik, karo, ortusme):
            karo_kutusu = (x1, y1, x2, y2)
            etiketler = []
            for indeks, kutu in enumerate(kutular):
                tasinan = kutuyu_karoya_tasi(kutu, karo_kutusu, min_gorunur)
                if tasinan is not None:
                    etiketler.append(tasinan)
                    yerlesen.add(indeks)
                elif gorunur_oran(kutu, karo_kutusu) > 0:
                    atlanan_etiket += 1

            if etiketler:
                pozitifler.append((yol, satir, sutun, karo_kutusu, etiketler))
            elif karo_kategorisi(kutular, karo_kutusu, min_gorunur) == "belirsiz":
                belirsizler.append((yol, satir, sutun, karo_kutusu))
            else:
                negatif_adaylar.append((yol, satir, sutun, karo_kutusu))

        for indeks, kutu_nesnesi in enumerate(kutu_nesneleri):
            if indeks not in yerlesen:
                butun_kalmayan.append({
                    "bolum": bolum,
                    "goruntu": yol.name,
                    "kutu_no": indeks,
                    "genislik_px": sayi_bicimle(kutu_nesnesi.genislik, 1),
                    "yukseklik_px": sayi_bicimle(kutu_nesnesi.yukseklik, 1),
                })

        if sira % ILERLEME_ARALIGI == 0 or sira == len(goruntuler):
            print(f"  [{bolum}] {sira}/{len(goruntuler)} goruntu planlandi", flush=True)

    return {
        "goruntu_sayisi": len(goruntuler),
        "pozitifler": pozitifler,
        "negatif_adaylar": negatif_adaylar,
        "belirsizler": belirsizler,
        "atlanan_etiket": atlanan_etiket,
        "butun_kalmayan": butun_kalmayan,
    }


def karolari_yaz(secilenler: list[tuple], goruntu_dizin: Path, etiket_dizin: Path) -> int:
    """Secilen karolari diske keser. Her kaynak goruntu yalnizca bir kez acilir."""
    from PIL import Image

    goruntu_dizin.mkdir(parents=True, exist_ok=True)
    etiket_dizin.mkdir(parents=True, exist_ok=True)

    goruntuye_gore: dict[Path, list[tuple]] = defaultdict(list)
    for kayit in secilenler:
        goruntuye_gore[kayit[0]].append(kayit)

    yazilan = 0
    toplam = len(goruntuye_gore)
    for sira, (yol, kayitlar) in enumerate(sorted(goruntuye_gore.items()), start=1):
        with Image.open(yol) as gorsel:
            gorsel = gorsel.convert("RGB")
            for _, satir, sutun, karo_kutusu, etiketler in kayitlar:
                ad = f"{yol.stem}_r{satir:02d}_c{sutun:02d}"
                gorsel.crop(karo_kutusu).save(goruntu_dizin / f"{ad}.jpg", quality=95)
                metin = "".join(
                    f"0 {xm:.6f} {ym:.6f} {g:.6f} {y:.6f}\n" for xm, ym, g, y in etiketler
                )
                (etiket_dizin / f"{ad}.txt").write_text(metin, encoding="utf-8")
                yazilan += 1
        if sira % ILERLEME_ARALIGI == 0 or sira == toplam:
            print(f"  {sira}/{toplam} kaynak goruntu kesildi ({yazilan} karo)", flush=True)
    return yazilan


def data_yaml_yaz(cikti: Path) -> Path:
    """Ultralytics'in bekledigi data.yaml dosyasini uretir."""
    hedef = cikti / "data.yaml"
    hedef.write_text(
        f"path: {cikti.resolve()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "nc: 1\n"
        "names:\n"
        "  0: human\n",
        encoding="utf-8",
    )
    return hedef


def manifest_satirlari(bolum: str, plan: dict, secilen_negatifler: set) -> list[dict]:
    """Manifest satirlarini uretir.

    Secilmeyen negatif karolar yazilmaz: karo 320'de goruntu basina 221 karo
    dusuyor ve bunlarin ezici cogunlugu bos arka plan. Hepsini yazmak yuz
    megabaytlik, bilgi tasimayan bir CSV uretirdi. Yazilan kumede pozitif,
    belirsiz ve gercekten kullanilan negatif karolarin hepsi var; disarida
    kalanlarin sayisi ozette raporlanir.
    """
    satirlar: list[dict] = []

    def satir(yol, s, c, kategori, etiket, atlanan, secildi):
        return {
            "bolum": bolum,
            "kaynak_goruntu": yol.name,
            "karo_satir": s,
            "karo_sutun": c,
            "kategori": kategori,
            "pozitif_mi": int(kategori == "pozitif"),
            "etiket_sayisi": etiket,
            "atlanan_etiket_sayisi": atlanan,
            "yazildi_mi": int(secildi),
        }

    for yol, s, c, _, etiketler in plan["pozitifler"]:
        satirlar.append(satir(yol, s, c, "pozitif", len(etiketler), 0, True))
    for yol, s, c, _ in plan["belirsizler"]:
        satirlar.append(satir(yol, s, c, "belirsiz", 0, 0, False))
    for yol, s, c, karo_kutusu in plan["negatif_adaylar"]:
        if (yol, s, c) in secilen_negatifler:
            satirlar.append(satir(yol, s, c, "negatif", 0, 0, True))
    return satirlar


def main() -> None:
    arg = argumanlari_coz()
    ortusme = ortusmeyi_sec(arg.karo, arg.ortusme)
    ortusme_px = ortusme_piksel(arg.karo, ortusme)
    onek = DENEME_ONEKI if arg.limit else ""

    cikti = arg.cikti or (PROJE_KOK / "data" / f"{onek}karo_{arg.karo}")

    print(f"Karo {arg.karo} px | ortusme {ortusme} ({ortusme_px} px) | "
          f"min-gorunur {arg.min_gorunur} | negatif orani {arg.negatif}x | tohum {TOHUM}")
    if ortusme_px <= MEDYAN_KUTU_PX:
        print(f"  UYARI: ortusme ({ortusme_px} px) medyan kutudan ({MEDYAN_KUTU_PX} px) "
              "buyuk degil. Karolar arasina dusen hedefler kaybolabilir.")
    else:
        print(f"  Ortusme medyan kutudan ({MEDYAN_KUTU_PX} px) buyuk: karolar arasina "
              "dusen hedef en az bir karoda butun kalabilir.")
    if arg.limit:
        print(f"  DENEME KOSUSU: bolum basina en fazla {arg.limit} goruntu. Uretilen "
              "veri kumesi gercek egitim kumesi DEGILDIR.")
    print(f"Cikti: {cikti}\n", flush=True)

    ozet: list[dict] = []
    tum_butun_kalmayan: list[dict] = []
    tum_manifest: list[dict] = []
    toplam = defaultdict(int)

    for kaynak_bolum, yolo_bolum in BOLUM_ESLESMESI.items():
        print(f"[{kaynak_bolum}] planlaniyor...", flush=True)
        plan = bolumu_planla(kaynak_bolum, arg.veri, arg.karo, ortusme,
                             arg.min_gorunur, arg.limit)

        istenen_negatif = len(plan["pozitifler"]) * arg.negatif
        secilen = negatif_ornekle(plan["negatif_adaylar"], istenen_negatif, TOHUM)
        secilen_anahtar = {(y, s, c) for y, s, c, _ in secilen}

        yazilacak = list(plan["pozitifler"]) + [(y, s, c, k, []) for y, s, c, k in secilen]
        print(f"[{kaynak_bolum}] {len(yazilacak)} karo kesiliyor...", flush=True)
        karolari_yaz(
            yazilacak,
            cikti / "images" / yolo_bolum,
            cikti / "labels" / yolo_bolum,
        )

        etiket_sayisi = sum(len(e) for *_, e in plan["pozitifler"])
        tum_butun_kalmayan += plan["butun_kalmayan"]
        tum_manifest += manifest_satirlari(kaynak_bolum, plan, secilen_anahtar)

        satir = {
            "bolum": f"{kaynak_bolum} -> {yolo_bolum}",
            "kaynak_goruntu": plan["goruntu_sayisi"],
            "pozitif_karo": len(plan["pozitifler"]),
            "negatif_aday": len(plan["negatif_adaylar"]),
            "negatif_secilen": len(secilen),
            "belirsiz_karo": len(plan["belirsizler"]),
            "yazilan_etiket": etiket_sayisi,
            "atlanan_etiket": plan["atlanan_etiket"],
            "butun_kalmayan_hedef": len(plan["butun_kalmayan"]),
        }
        ozet.append(satir)
        for ad, deger in satir.items():
            if ad != "bolum":
                toplam[ad] += deger

    data_yaml = data_yaml_yaz(cikti)

    kosu = kosu_bilgisi(
        karo_boyutu=arg.karo,
        ortusme_orani=ortusme,
        ortusme_piksel=ortusme_px,
        min_gorunur=arg.min_gorunur,
        negatif_orani=arg.negatif,
        tohum=TOHUM,
        limit=arg.limit,
        cikti_dizini=str(cikti),
        medyan_kutu_px=MEDYAN_KUTU_PX,
        manifest_kapsami=(
            "pozitif + belirsiz + secilen negatif karolar; secilmeyen negatif "
            "adaylar yazilmadi, sayilari ozet satirindadir"
        ),
        gecerlilik_notu=(
            f"alt kume ({arg.limit} goruntu/bolum) uzerinde uretildi, egitim kumesi degildir"
            if arg.limit else "train ve valid bolumlerinin tamami islendi"
        ),
    )
    manifest = csv_yaz(RAPOR_KOK / f"{onek}karo_veri_manifest_{arg.karo}.csv", tum_manifest, kosu)

    print("\n=== OZET ===")
    tablo_bas(ozet + [{"bolum": "TOPLAM", **dict(toplam)}])
    print(f"\ndata.yaml : {data_yaml}")
    print(f"Manifest  : {manifest}  ({len(tum_manifest)} satir)")

    butun_kalmayan = len(tum_butun_kalmayan)
    print(f"\nHicbir karoda butun kalmayan hedef: {butun_kalmayan}")
    if butun_kalmayan:
        print("  Bu hedefler egitim verisinde HIC gorunmuyor. Yukseklige gore sirali:")
        for kayit in sorted(tum_butun_kalmayan, key=lambda k: -k["yukseklik_px"]):
            print(f"    {kayit['bolum']:>5}  {kayit['goruntu']}  kutu {kayit['kutu_no']}  "
                  f"{kayit['genislik_px']}x{kayit['yukseklik_px']} px")
    else:
        print("  Beklenen sonuc: ortusme medyan kutudan buyuk oldugu icin her hedef "
              "en az bir karoda butun kaldi.")


if __name__ == "__main__":
    main()
