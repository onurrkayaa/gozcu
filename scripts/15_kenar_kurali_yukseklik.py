"""%60 min-gorunur kenar kuralinin hedef yuksekligine gore etkisini olcer.

OLCULEN HIPOTEZ: "%60 min-gorunur kenar kurali, >=80 px hedeflerin egitim
orneklerini diger yukseklik bantlarina gore daha fazla azaltiyor olabilir."

Bu script YALNIZCA EGITIM VERISI tarafini olcer. Recall ile nedensellik burada
olculmez; bant sonuclari recall dususunun sebebi olarak sunulamaz.

Kapsam: karo 512, yalnizca train ve valid bolumleri. Test bolumu egitim verisi
degildir ve bu analize girmez.

Hicbir geometri yeniden yazilmaz:
- Karo koordinatlari backend/core/tiling.py icindeki karolari_hesapla'dan gelir.
- %60 karari 11_karo_veri_hazirla.py icindeki kutuyu_karoya_tasi/gorunur_oran
  ile verilir; egitim kumesini ureten hesabin ta kendisidir.
- Yukseklik bant sinirlari reports/yukseklik_kazanim.csv'den okunur.
- Karo boyutu, ortusme ve min-gorunur esigi manifestin kosu_ sutunlarindan
  okunur; burada ikinci kez tanimlanmaz.

Yeni karo goruntusu veya etiketi YAZILMAZ; analiz bellekte yapilir.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
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

from core.tiling import karolari_hesapla  # noqa: E402


def _karo_veri_modulu():
    """11_karo_veri_hazirla.py'yi yoldan yukler (dosya adi rakamla basliyor).

    Gorunurluk kurali ve karo-etiket cevrimi oradan ALINIR; kopyalanmaz."""
    spec = importlib.util.spec_from_file_location(
        "karo_veri", SCRIPT_DIZIN / "11_karo_veri_hazirla.py"
    )
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


KARO_VERI = _karo_veri_modulu()

# Egitim verisini ureten bolumler. Test bolumu karolanmaz, buraya girmez.
BOLUMLER = ("train", "valid")

VARSAYILAN_MANIFEST = RAPOR_KOK / "karo_veri_manifest_512.csv"
VARSAYILAN_BANT_CSV = RAPOR_KOK / "yukseklik_kazanim.csv"
VARSAYILAN_LOG = RAPOR_KOK / "11_karo_veri_512.log"
VARSAYILAN_ISTATISTIK = RAPOR_KOK / "veri_istatistik.csv"

TOPLAM_SATIRI = "TOPLAM"
ILERLEME_ARALIGI = 200


def argumanlari_coz() -> argparse.Namespace:
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Karo 512 egitim kumesinde %60 min-gorunur kuralinin hedef yuksekligine "
            "gore etkisini olcer. Model calistirmaz, karo yazmaz."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Veri kumesi kok klasoru")
    ayrastirici.add_argument(
        "--manifest", type=Path, default=VARSAYILAN_MANIFEST,
        help="Karo 512 manifesti; karo parametreleri ve capraz kontrol buradan okunur",
    )
    ayrastirici.add_argument(
        "--bant-csv", type=Path, default=VARSAYILAN_BANT_CSV,
        help="Yukseklik bant sinirlarinin okundugu CSV",
    )
    ayrastirici.add_argument(
        "--kosu-log", type=Path, default=VARSAYILAN_LOG,
        help="11_karo_veri_hazirla.py kosu gunlugu; atlanan ve kaybolan sayilari buradadir",
    )
    ayrastirici.add_argument(
        "--istatistik", type=Path, default=VARSAYILAN_ISTATISTIK,
        help="Bolum basina hedef sayisinin okundugu mevcut olcum CSV'si",
    )
    ayrastirici.add_argument(
        "--cikti", type=Path, default=RAPOR_KOK / "kenar_kurali_yukseklik.csv",
        help="Sonuc CSV dosyasinin yolu",
    )
    return ayrastirici.parse_args()


# --- Girdi okuma --------------------------------------------------------------


def bant_sinirlari(bant_csv: Path) -> list[tuple[str, float, float]]:
    """Bant etiketlerini mevcut CSV'den okur ve (etiket, alt, ust) olarak cozer.

    Sinirlar burada ikinci kez tanimlanmaz: '<44', '44-55', '>=80' bicimindeki
    etiketler oldugu gibi ayristirilir. Bantlar alt sinira gore siralanir."""
    etiketler: list[str] = []
    for satir in csv.DictReader(bant_csv.open(encoding="utf-8")):
        etiket = satir["yukseklik_bandi_px"]
        if etiket not in etiketler:
            etiketler.append(etiket)

    bantlar: list[tuple[str, float, float]] = []
    for etiket in etiketler:
        if etiket.startswith("<"):
            bantlar.append((etiket, -math.inf, float(etiket[1:])))
        elif etiket.startswith(">="):
            bantlar.append((etiket, float(etiket[2:]), math.inf))
        else:
            alt, ust = etiket.split("-")
            bantlar.append((etiket, float(alt), float(ust)))
    if not bantlar:
        raise SystemExit(f"Bant etiketi bulunamadi: {bant_csv}")
    return sorted(bantlar, key=lambda b: b[1])


def bandi_bul(yukseklik: float, bantlar: list[tuple[str, float, float]]) -> str:
    """Kutu yuksekligini bantlardan birine yerlestirir; ust sinir haric tutulur."""
    for etiket, alt, ust in bantlar:
        if alt <= yukseklik < ust:
            return etiket
    raise ValueError(f"Yukseklik hicbir banda girmedi: {yukseklik}")


def karo_parametreleri(manifest: Path) -> dict[str, float]:
    """Karo boyutu, ortusme ve min-gorunur esigini manifestin kosu_ sutunlarindan
    okur. Bu degerler burada yeniden tanimlanmaz; egitim kumesini ureten kosunun
    kendi kaydidir."""
    with manifest.open(encoding="utf-8") as dosya:
        ilk = next(csv.DictReader(dosya), None)
    if ilk is None:
        raise SystemExit(f"Manifest bos: {manifest}")
    return {
        "karo": int(ilk["kosu_karo_boyutu"]),
        "ortusme": float(ilk["kosu_ortusme_orani"]),
        "min_gorunur": float(ilk["kosu_min_gorunur"]),
        "kosu_komut": ilk["kosu_komut"],
    }


def manifest_gecerli_etiket(manifest: Path, bolumler=BOLUMLER) -> int:
    """Manifeste yazilmis gecerli karo-etiket toplami."""
    toplam = 0
    with manifest.open(encoding="utf-8") as dosya:
        for satir in csv.DictReader(dosya):
            if satir["bolum"] in bolumler:
                toplam += int(satir["etiket_sayisi"])
    return toplam


def log_toplamlari(kosu_log: Path) -> dict[str, int]:
    """Kosu gunlugundeki OZET tablosunun TOPLAM satirini okur.

    Atlanan hedef ornegi ve hicbir karoda butun kalmayan hedef sayisi yalnizca
    bu ozette kayitlidir: manifestin atlanan_etiket_sayisi sutunu her satirda
    sifir yazilir (11_karo_veri_hazirla.py o alani karo bazinda doldurmaz)."""
    if not kosu_log.is_file():
        raise SystemExit(f"Kosu gunlugu bulunamadi: {kosu_log}")
    basliklar: list[str] | None = None
    for satir in kosu_log.read_text(encoding="utf-8").splitlines():
        if "|" not in satir:
            continue
        hucreler = [h.strip() for h in satir.split("|")]
        if hucreler[0] == "bolum":
            basliklar = hucreler
        elif basliklar and hucreler[0] == TOPLAM_SATIRI:
            return {
                ad: int(deger)
                for ad, deger in zip(basliklar[1:], hucreler[1:])
            }
    raise SystemExit(f"Gunlukte OZET TOPLAM satiri bulunamadi: {kosu_log}")


def istatistik_hedef_toplami(istatistik: Path, bolumler=BOLUMLER) -> int:
    """Mevcut veri istatistigi CSV'sinden train+valid hedef toplamini okur."""
    toplam = 0
    for satir in csv.DictReader(istatistik.open(encoding="utf-8")):
        if satir["bolum"] in bolumler:
            toplam += int(satir["toplam_kutu"])
    return toplam


# --- Hedef izleme -------------------------------------------------------------


def hedefleri_oku(etiket_dosya: Path, genislik: int, yukseklik: int) -> list[tuple[int, object]]:
    """(etiket satir numarasi, Kutu) ciftleri. Kutular ortak.yolo_etiket_oku ile
    uretilir; satir numaralari ayni kabul kuralina (en az 5 alan) gore sayilir."""
    kutular = yolo_etiket_oku(etiket_dosya, genislik, yukseklik)
    if not etiket_dosya.is_file():
        return []
    satir_nolari = [
        no for no, satir in enumerate(
            etiket_dosya.read_text(encoding="utf-8").splitlines(), start=1
        )
        if len(satir.split()) >= 5
    ]
    if len(satir_nolari) != len(kutular):
        raise ValueError(
            f"Etiket satiri ve kutu sayisi uyusmadi: {etiket_dosya} "
            f"({len(satir_nolari)} satir, {len(kutular)} kutu)"
        )
    return list(zip(satir_nolari, kutular))


def hedef_kimligi(bolum: str, goreli_yol: str, satir_no: int) -> str:
    """Bir hedefi benzersiz kilan kimlik: bolum + goreli goruntu yolu + satir no."""
    return f"{bolum}|{goreli_yol}|{satir_no}"


def hedefleri_izle(veri_kok: Path, karo: int, ortusme: float, min_gorunur: float,
                   bantlar: list[tuple[str, float, float]], bolumler=BOLUMLER,
                   ilerleme: bool = False) -> list[dict]:
    """Her benzersiz hedef icin kesisen karo, gecerli karo-etiket ve atlanan
    ornek sayilarini cikarir. Karo goruntusu veya etiketi YAZILMAZ."""
    from PIL import Image

    kayitlar: list[dict] = []
    for bolum in bolumler:
        goruntu_dizin, etiket_dizin = bolum_yolu(bolum, veri_kok)
        goruntuler = goruntuleri_listele(goruntu_dizin)
        for sira, yol in enumerate(goruntuler, start=1):
            with Image.open(yol) as gorsel:
                genislik, yukseklik = gorsel.size
            hedefler = hedefleri_oku(etiket_yolu(yol, etiket_dizin), genislik, yukseklik)
            if hedefler:
                karolar = karolari_hesapla(genislik, yukseklik, karo, ortusme)
            goreli_yol = yol.relative_to(veri_kok).as_posix()

            for satir_no, kutu in hedefler:
                kutu_dortlusu = (kutu.x1, kutu.y1, kutu.x2, kutu.y2)
                kesisen = gecerli = atlanan = 0
                for _, _, x1, y1, x2, y2 in karolar:
                    karo_kutusu = (x1, y1, x2, y2)
                    # Karar 11_karo_veri_hazirla.py'nin kendi hesabiyla verilir.
                    tasinan = KARO_VERI.kutuyu_karoya_tasi(
                        kutu_dortlusu, karo_kutusu, min_gorunur
                    )
                    if tasinan is not None:
                        kesisen += 1
                        gecerli += 1
                    elif KARO_VERI.gorunur_oran(kutu_dortlusu, karo_kutusu) > 0:
                        kesisen += 1
                        atlanan += 1
                kayitlar.append({
                    "bolum": bolum,
                    "goreli_yol": goreli_yol,
                    "hedef_kimligi": hedef_kimligi(bolum, goreli_yol, satir_no),
                    "kutu_yukseklik_px": sayi_bicimle(kutu.yukseklik, 1),
                    "yukseklik_bandi": bandi_bul(kutu.yukseklik, bantlar),
                    "kesisen_karo": kesisen,
                    "gecerli_karo_etiket": gecerli,
                    "atlanan_hedef_ornegi": atlanan,
                    "kenar_kuralindan_etkilendi": atlanan > 0,
                    "en_az_bir_gecerli_ornek": gecerli > 0,
                    "tamamen_kayboldu": gecerli == 0,
                })
            if ilerleme and (sira % ILERLEME_ARALIGI == 0 or sira == len(goruntuler)):
                print(f"  [{bolum}] {sira}/{len(goruntuler)} goruntu tarandi", flush=True)
    return kayitlar


# --- Bant toplamlari ----------------------------------------------------------


def bant_satiri(etiket: str, kayitlar: list[dict]) -> dict:
    """Bir bant (veya tum kayitlar) icin ozet satiri; oranlari da hesaplar."""
    hedef = len(kayitlar)
    kesisen = sum(k["kesisen_karo"] for k in kayitlar)
    gecerli = sum(k["gecerli_karo_etiket"] for k in kayitlar)
    atlanan = sum(k["atlanan_hedef_ornegi"] for k in kayitlar)
    etkilenen = sum(1 for k in kayitlar if k["kenar_kuralindan_etkilendi"])
    kalan = sum(1 for k in kayitlar if k["en_az_bir_gecerli_ornek"])
    kaybolan = sum(1 for k in kayitlar if k["tamamen_kayboldu"])
    return {
        "yukseklik_bandi": etiket,
        "benzersiz_hedef_sayisi": hedef,
        "toplam_kesisen_karo": kesisen,
        "gecerli_karo_etiket_sayisi": gecerli,
        "atlanan_hedef_ornegi_sayisi": atlanan,
        "en_az_bir_kez_etkilenen_hedef_sayisi": etkilenen,
        "en_az_bir_gecerli_ornegi_olan_hedef_sayisi": kalan,
        "tamamen_kaybolan_hedef_sayisi": kaybolan,
        "hedef_basina_gecerli_ornek": sayi_bicimle(gecerli / hedef, 4) if hedef else 0.0,
        "etkilenen_hedef_orani": sayi_bicimle(etkilenen / hedef, 4) if hedef else 0.0,
        "atlanan_ornek_orani": sayi_bicimle(atlanan / kesisen, 4) if kesisen else 0.0,
    }


def bant_satirlari(kayitlar: list[dict], bantlar: list[tuple[str, float, float]]) -> list[dict]:
    """Bant sirasi sabittir (alt sinira gore artan); sonda TOPLAM satiri gelir."""
    gruplar: dict[str, list[dict]] = defaultdict(list)
    for kayit in kayitlar:
        gruplar[kayit["yukseklik_bandi"]].append(kayit)
    satirlar = [bant_satiri(etiket, gruplar[etiket]) for etiket, _, _ in bantlar]
    satirlar.append(bant_satiri(TOPLAM_SATIRI, kayitlar))
    return satirlar


# --- Capraz kontrol ve hipotez karari -----------------------------------------


def capraz_kontrol(kayitlar: list[dict], mevcut: dict[str, int]) -> list[dict]:
    """Yeni analizin toplamlarini mevcut kayitlarla karsilastirir."""
    yeni = {
        "benzersiz_hedef": len(kayitlar),
        "gecerli_karo_etiket": sum(k["gecerli_karo_etiket"] for k in kayitlar),
        "atlanan_hedef_ornegi": sum(k["atlanan_hedef_ornegi"] for k in kayitlar),
        "tamamen_kaybolan_hedef": sum(1 for k in kayitlar if k["tamamen_kayboldu"]),
    }
    return [
        {
            "olcu": ad,
            "mevcut_kayit": mevcut[ad],
            "yeni_analiz": yeni[ad],
            "sonuc": "UYUSTU" if mevcut[ad] == yeni[ad] else "UYUSMADI",
        }
        for ad in yeni
    ]


def hipotez_karari(satirlar: list[dict], bantlar: list[tuple[str, float, float]]) -> dict:
    """Son bandi (>=80 px) kendinden onceki bantla iki metrikte karsilastirir.

    Olumsuz yon: etkilenen hedef orani DAHA YUKSEK, hedef basina gecerli ornek
    DAHA DUSUK."""
    if len(bantlar) < 2:
        return {"karar": "OLCULEMEDI", "sebep": "karsilastirilacak iki bant yok"}

    ad_son, ad_onceki = bantlar[-1][0], bantlar[-2][0]
    bul = {s["yukseklik_bandi"]: s for s in satirlar}
    son, onceki = bul[ad_son], bul[ad_onceki]
    if not son["benzersiz_hedef_sayisi"] or not onceki["benzersiz_hedef_sayisi"]:
        return {
            "karar": "OLCULEMEDI",
            "sebep": f"{ad_son} veya {ad_onceki} bandinda hedef yok",
            "son_bant": ad_son, "onceki_bant": ad_onceki,
        }

    oran_daha_kotu = son["etkilenen_hedef_orani"] > onceki["etkilenen_hedef_orani"]
    ornek_daha_kotu = son["hedef_basina_gecerli_ornek"] < onceki["hedef_basina_gecerli_ornek"]
    if oran_daha_kotu and ornek_daha_kotu:
        karar = "DESTEKLENDI"
    elif not oran_daha_kotu and not ornek_daha_kotu:
        karar = "CURUTULDU"
    else:
        karar = "KARISIK SONUC"
    return {
        "karar": karar,
        "son_bant": ad_son,
        "onceki_bant": ad_onceki,
        "etkilenen_hedef_orani_daha_kotu": oran_daha_kotu,
        "hedef_basina_gecerli_ornek_daha_kotu": ornek_daha_kotu,
    }


def main() -> None:
    arg = argumanlari_coz()

    bantlar = bant_sinirlari(arg.bant_csv)
    parametre = karo_parametreleri(arg.manifest)
    karo, ortusme = parametre["karo"], parametre["ortusme"]
    min_gorunur = parametre["min_gorunur"]
    ortusme_px = KARO_VERI.ortusme_piksel(karo, ortusme)

    print(f"Karo {karo} px | ortusme {ortusme} ({ortusme_px} px) | "
          f"min-gorunur {min_gorunur} | bolumler {', '.join(BOLUMLER)}")
    print(f"Parametreler manifestten okundu: {arg.manifest.name}")
    print(f"Bant sinirlari okundu ({arg.bant_csv.name}): "
          f"{', '.join(e for e, _, _ in bantlar)}")
    print("Yeni tarama yok, karo yazilmiyor; geometri bellekte hesaplaniyor.\n", flush=True)

    kayitlar = hedefleri_izle(arg.veri, karo, ortusme, min_gorunur, bantlar, ilerleme=True)
    satirlar = bant_satirlari(kayitlar, bantlar)

    mevcut = {
        "benzersiz_hedef": istatistik_hedef_toplami(arg.istatistik),
        "gecerli_karo_etiket": manifest_gecerli_etiket(arg.manifest),
    }
    log = log_toplamlari(arg.kosu_log)
    mevcut["atlanan_hedef_ornegi"] = log["atlanan_etiket"]
    mevcut["tamamen_kaybolan_hedef"] = log["butun_kalmayan_hedef"]

    kontrol = capraz_kontrol(kayitlar, mevcut)
    print("\n=== CAPRAZ KONTROL ===")
    tablo_bas(kontrol)
    print(f"Mevcut kayit kaynaklari: benzersiz hedef -> {arg.istatistik.name}, "
          f"gecerli karo-etiket -> {arg.manifest.name}, "
          f"atlanan ve kaybolan -> {arg.kosu_log.name} (manifestin "
          "atlanan_etiket_sayisi sutunu her satirda sifirdir)")

    if any(s["sonuc"] == "UYUSMADI" for s in kontrol):
        print("\nUYUSMAZLIK VAR. Eski dosyalar degistirilmedi, CSV yazilmadi.")
        sys.exit(1)

    kosu = kosu_bilgisi(
        karo_boyutu=karo,
        ortusme_orani=ortusme,
        ortusme_piksel=ortusme_px,
        min_gorunur=min_gorunur,
        bolumler=",".join(BOLUMLER),
        girdi=(
            f"{arg.manifest.as_posix()} + {arg.bant_csv.as_posix()} + "
            f"{arg.kosu_log.as_posix()} + {arg.istatistik.as_posix()} + "
            f"{arg.veri.as_posix()}"
        ),
        kaynak_manifest=arg.manifest.as_posix(),
        manifest_kosu_komut=parametre["kosu_komut"],
        tarama_notu=(
            "yeni model taramasi ve yeni karolama yok; karo geometrisi bellekte "
            "yeniden hesaplandi, karo goruntusu veya etiketi yazilmadi"
        ),
        hedef_kimligi="bolum + goreli goruntu yolu + etiket satir numarasi",
        kapsam_notu=(
            "yalnizca egitim verisi (train + valid) olculdu; recall ile nedensellik "
            "bu olcumde yer almaz"
        ),
    )
    cikti = csv_yaz(arg.cikti, satirlar, kosu)

    print("\n=== BANT KIRILIMI ===")
    tablo_bas(satirlar)

    karar = hipotez_karari(satirlar, bantlar)
    print(f"\nCSV: {cikti}  ({len(satirlar)} satir)")
    print("\n=== HIPOTEZ ===")
    print(f"Karsilastirma: {karar.get('son_bant', '?')} vs {karar.get('onceki_bant', '?')}")
    print(f"Karar: {karar['karar']}")
    if karar["karar"] == "DESTEKLENDI":
        print("Egitim verisi davranisi hipotezle ayni yonde.")
    print("Recall ile nedensellik: bu olcumde olculmedi.")


if __name__ == "__main__":
    main()
