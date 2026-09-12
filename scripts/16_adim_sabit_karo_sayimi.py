"""Adim sabit tutularak karo boyutunun egitim verisi hazirlamaya etkisini sayar.

Karsilastirilan iki kosul:
    karo 320 / ortusme 0,25
    karo 512 / ortusme 0,53125
Ikisinde de karo ADIMI ayni cikar; degisen tek sey karo boyutudur. Adim bu
dosyada ayrica hesaplanmaz: 11_karo_veri_hazirla.py'nin ortusme_piksel islevi
kullanilir, o da degeri gercek karolamadan geri okur.

YALNIZCA SAYIM. Karo goruntusu, etiket dosyasi veya cikti veri klasoru
uretilmez; 11_karo_veri_hazirla.py'nin plan gecisi (bolumu_planla) zaten diske
dokunmaz ve oldugu gibi cagrilir. Uretim davranisi degistirilmedi.

Sonuc yalnizca EGITIM VERISI HAZIRLAMA davranisini gosterir. Recall veya model
ustunlugu bu olcumde yer almaz.
"""

from __future__ import annotations

import argparse
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
    kosu_bilgisi,
    sayi_bicimle,
    tablo_bas,
)


def _modul_yukle(ad: str, dosya: str):
    """Rakamla baslayan script dosyalarini yoldan yukler."""
    spec = importlib.util.spec_from_file_location(ad, SCRIPT_DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# Karolama, gorunurluk kurali ve karo siniflari 11'den; hedef bazinda izleme
# 15'ten alinir. Hicbiri burada yeniden yazilmaz.
KARO_VERI = _modul_yukle("karo_veri", "11_karo_veri_hazirla.py")
KENAR = _modul_yukle("kenar_kurali", "15_kenar_kurali_yukseklik.py")

# Deney kosullari: (karo boyutu, ortusme orani). Ikisinin de adimi ayni olmali.
KOSULLAR = ((320, 0.25), (512, 0.53125))

# Egitim verisini ureten bolumler; test bolumu karolanmaz.
BOLUMLER = ("train", "valid")

MIN_GORUNUR = 0.6

# 15'in hedef izleme islevi bant kirilimi bekler. Bu olcumde bant ayrimi yok;
# tek bir kapsayici bant verilerek ayni islev yeniden kullanilir.
TEK_BANT = [("hepsi", -math.inf, math.inf)]

VARSAYILAN_MANIFEST_320 = RAPOR_KOK / "karo_veri_manifest_320.csv"
VARSAYILAN_LOG_320 = RAPOR_KOK / "11_karo_veri_320.log"
VARSAYILAN_ISTATISTIK = RAPOR_KOK / "veri_istatistik.csv"


def argumanlari_coz() -> argparse.Namespace:
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Adim sabitken karo boyutunun egitim verisi hazirlamaya etkisini sayar. "
            "Dosya yazmaz, model calistirmaz."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Veri kumesi kok klasoru")
    ayrastirici.add_argument(
        "--manifest-320", type=Path, default=VARSAYILAN_MANIFEST_320,
        help="Karo 320 manifesti; capraz kontrolde kullanilir",
    )
    ayrastirici.add_argument(
        "--log-320", type=Path, default=VARSAYILAN_LOG_320,
        help="Karo 320 kosu gunlugu; karo ve atlanan sayilari buradan okunur",
    )
    ayrastirici.add_argument(
        "--istatistik", type=Path, default=VARSAYILAN_ISTATISTIK,
        help="Bolum basina hedef sayisinin okundugu mevcut olcum CSV'si",
    )
    ayrastirici.add_argument(
        "--cikti", type=Path, default=RAPOR_KOK / "adim_sabit_karsilastirma.csv",
        help="Sonuc CSV dosyasinin yolu",
    )
    return ayrastirici.parse_args()


# --- Sayim --------------------------------------------------------------------


def adim_piksel(karo: int, ortusme: float) -> int:
    """Karo adimi. Ortusme pikseli 11'in kendi islevinden gelir; formul burada
    ikinci kez yazilmaz."""
    return karo - KARO_VERI.ortusme_piksel(karo, ortusme)


def belirsiz_karoya_dusen_hedefler(plan: dict, bolum: str, veri_kok: Path,
                                   min_gorunur: float) -> set[str]:
    """En az bir BELIRSIZ karoya dusen benzersiz hedeflerin kimlikleri.

    Belirsiz karo: icinde hedef var ama hicbiri %60 kuralini gecemiyor. Bu karo
    hicbir yere yazilmaz. Hedefin oraya dusmesi, o karoda kesismesi demektir."""
    from PIL import Image

    _, etiket_dizin = bolum_yolu(bolum, veri_kok)
    goruntuye_gore: dict[Path, list[tuple]] = defaultdict(list)
    for yol, _, _, karo_kutusu in plan["belirsizler"]:
        goruntuye_gore[yol].append(karo_kutusu)

    kimlikler: set[str] = set()
    for yol, karolar in goruntuye_gore.items():
        with Image.open(yol) as gorsel:
            genislik, yukseklik = gorsel.size
        goreli_yol = yol.relative_to(veri_kok).as_posix()
        for satir_no, kutu in KENAR.hedefleri_oku(
            etiket_yolu(yol, etiket_dizin), genislik, yukseklik
        ):
            kutu_dortlusu = (kutu.x1, kutu.y1, kutu.x2, kutu.y2)
            if any(
                KARO_VERI.gorunur_oran(kutu_dortlusu, karo) > 0 for karo in karolar
            ):
                kimlikler.add(KENAR.hedef_kimligi(bolum, goreli_yol, satir_no))
    return kimlikler


def kosulu_say(veri_kok: Path, karo: int, ortusme: float,
               min_gorunur: float = MIN_GORUNUR, bolumler=BOLUMLER,
               ilerleme: bool = False) -> dict:
    """Bir karo/ortusme kosulunun karo ve hedef sayimlarini cikarir.

    Karo siniflari 11'in plan gecisinden (bolumu_planla) gelir: uretim kosusunun
    kullandigi tanimlarin ta kendisi. Negatif ornekleme YAPILMAZ; negatif aday
    sayisi oldugu gibi raporlanir."""
    goruntu = pozitif = belirsiz = negatif_aday = atlanan_karo_ici = 0
    belirsiz_hedefler: set[str] = set()

    for bolum in bolumler:
        plan = KARO_VERI.bolumu_planla(bolum, veri_kok, karo, ortusme, min_gorunur, 0)
        goruntu += plan["goruntu_sayisi"]
        pozitif += len(plan["pozitifler"])
        belirsiz += len(plan["belirsizler"])
        negatif_aday += len(plan["negatif_adaylar"])
        atlanan_karo_ici += plan["atlanan_etiket"]
        belirsiz_hedefler |= belirsiz_karoya_dusen_hedefler(
            plan, bolum, veri_kok, min_gorunur
        )
        if ilerleme:
            print(f"  [{bolum}] karo {karo}: plan cikarildi", flush=True)

    # Hedef bazinda sayim 15'in izleme islevinden gelir; her hedef bir kez sayilir.
    hedefler = KENAR.hedefleri_izle(
        veri_kok, karo, ortusme, min_gorunur, TEK_BANT, bolumler=bolumler
    )
    benzersiz = len(hedefler)
    gecerli = sum(h["gecerli_karo_etiket"] for h in hedefler)
    atlanan = sum(h["atlanan_hedef_ornegi"] for h in hedefler)
    kalan = sum(1 for h in hedefler if h["en_az_bir_gecerli_ornek"])
    kaybolan = sum(1 for h in hedefler if h["tamamen_kayboldu"])

    if atlanan != atlanan_karo_ici:
        raise ValueError(
            "Atlanan hedef ornegi sayisi plan gecisiyle hedef izlemesi arasinda "
            f"uyusmadi: {atlanan_karo_ici} != {atlanan}"
        )

    return {
        "kosul": f"karo {karo} / ortusme {ortusme}",
        "karo_boyutu": karo,
        "ortusme": ortusme,
        "ortusme_piksel": KARO_VERI.ortusme_piksel(karo, ortusme),
        "adim_piksel": adim_piksel(karo, ortusme),
        "kaynak_goruntu_sayisi": goruntu,
        "benzersiz_hedef_sayisi": benzersiz,
        "planlanan_toplam_karo": pozitif + belirsiz + negatif_aday,
        "pozitif_karo": pozitif,
        "belirsiz_karo": belirsiz,
        "negatif_aday_karo": negatif_aday,
        "gecerli_karo_etiket_sayisi": gecerli,
        "atlanan_hedef_ornegi_sayisi": atlanan,
        "en_az_bir_belirsiz_karoya_dusen_benzersiz_hedef": len(belirsiz_hedefler),
        "en_az_bir_gecerli_ornegi_olan_benzersiz_hedef": kalan,
        "tamamen_kaybolan_benzersiz_hedef": kaybolan,
        "hedef_basina_gecerli_karo_etiket": sayi_bicimle(gecerli / benzersiz, 4) if benzersiz else 0.0,
        "belirsiz_karoya_dusen_hedef_orani": sayi_bicimle(
            len(belirsiz_hedefler) / benzersiz, 4) if benzersiz else 0.0,
    }


# --- Capraz kontrol -----------------------------------------------------------


def capraz_kontrol_320(satir: dict, log: dict, benzersiz_hedef: int,
                       manifest_etiket: int) -> list[dict]:
    """Karo 320 sayimini daha once kaydedilmis kosunun sonuclariyla karsilastirir."""
    beklenen = [
        ("kaynak_goruntu_sayisi", log["kaynak_goruntu"], "11_karo_veri_320.log"),
        ("benzersiz_hedef_sayisi", benzersiz_hedef, "veri_istatistik.csv"),
        ("planlanan_toplam_karo",
         log["pozitif_karo"] + log["belirsiz_karo"] + log["negatif_aday"],
         "11_karo_veri_320.log (pozitif + belirsiz + negatif aday)"),
        ("pozitif_karo", log["pozitif_karo"], "11_karo_veri_320.log"),
        ("belirsiz_karo", log["belirsiz_karo"], "11_karo_veri_320.log"),
        ("gecerli_karo_etiket_sayisi", log["yazilan_etiket"], "11_karo_veri_320.log"),
        ("gecerli_karo_etiket_sayisi", manifest_etiket,
         "karo_veri_manifest_320.csv (etiket_sayisi toplami)"),
        ("atlanan_hedef_ornegi_sayisi", log["atlanan_etiket"], "11_karo_veri_320.log"),
        ("tamamen_kaybolan_benzersiz_hedef", log["butun_kalmayan_hedef"],
         "11_karo_veri_320.log"),
    ]
    return [
        {
            "olcu": ad,
            "mevcut_kayit": deger,
            "kaynak": kaynak,
            "yeni_sayim": satir[ad],
            "sonuc": "UYUSTU" if satir[ad] == deger else "UYUSMADI",
        }
        for ad, deger, kaynak in beklenen
    ]


def sonuc_etiketi(satirlar: list[dict]) -> dict:
    """Iki kosulu belirsiz karoya dusen hedef orani ve hedef basina gecerli
    karo-etiket sayisinda karsilastirir.

    Olumsuz yon: oran DAHA YUKSEK, hedef basina ornek DAHA DUSUK."""
    if len(satirlar) != 2:
        return {"etiket": "OLCULEMEDI", "sebep": "iki kosul birden olculemedi"}
    a, b = satirlar
    if not a["benzersiz_hedef_sayisi"] or not b["benzersiz_hedef_sayisi"]:
        return {"etiket": "OLCULEMEDI", "sebep": "benzersiz hedef sayisi sifir"}

    oran_a, oran_b = a["belirsiz_karoya_dusen_hedef_orani"], b["belirsiz_karoya_dusen_hedef_orani"]
    ornek_a, ornek_b = a["hedef_basina_gecerli_karo_etiket"], b["hedef_basina_gecerli_karo_etiket"]

    if oran_a == oran_b and ornek_a == ornek_b:
        etiket = "ESIT"
    elif oran_a > oran_b and ornek_a < ornek_b:
        etiket = f"KARO {a['karo_boyutu']} DAHA FAZLA ETKILENIYOR"
    elif oran_b > oran_a and ornek_b < ornek_a:
        etiket = f"KARO {b['karo_boyutu']} DAHA FAZLA ETKILENIYOR"
    else:
        etiket = "KARISIK SONUC"
    return {
        "etiket": etiket,
        "belirsiz_orani": {a["karo_boyutu"]: oran_a, b["karo_boyutu"]: oran_b},
        "hedef_basina_ornek": {a["karo_boyutu"]: ornek_a, b["karo_boyutu"]: ornek_b},
    }


def main() -> None:
    arg = argumanlari_coz()

    adimlar = {karo: adim_piksel(karo, ortusme) for karo, ortusme in KOSULLAR}
    if len(set(adimlar.values())) != 1:
        raise SystemExit(
            f"Kosullarin adimi ayni degil: {adimlar}. Karsilastirma adim sabitken gecerlidir."
        )
    adim = next(iter(adimlar.values()))
    print(f"Kosullar: " + " | ".join(f"karo {k} / ortusme {o}" for k, o in KOSULLAR))
    print(f"Adim (mevcut karolama kodundan): {adim} px, iki kosulda da ayni")
    print(f"min-gorunur {MIN_GORUNUR} | bolumler {', '.join(BOLUMLER)}")
    print("Sayim kipi: karo goruntusu, etiket veya cikti klasoru uretilmiyor.\n", flush=True)

    satirlar = []
    for karo, ortusme in KOSULLAR:
        print(f"[karo {karo} / ortusme {ortusme}] sayiliyor...", flush=True)
        satirlar.append(kosulu_say(arg.veri, karo, ortusme, ilerleme=True))

    log320 = KENAR.log_toplamlari(arg.log_320)
    kontrol = capraz_kontrol_320(
        satirlar[0],
        log320,
        KENAR.istatistik_hedef_toplami(arg.istatistik, BOLUMLER),
        KENAR.manifest_gecerli_etiket(arg.manifest_320, BOLUMLER),
    )
    print("\n=== KARO 320 CAPRAZ KONTROLU ===")
    tablo_bas(kontrol)
    print("Manifestin atlanan_etiket_sayisi sutunu her satirda sifirdir; atlanan "
          "hedef ornegi ve kaybolan hedef kosu gunlugundeki OZET satirindan alindi.")

    if any(s["sonuc"] == "UYUSMADI" for s in kontrol):
        print("\nUYUSMAZLIK VAR. Eski dosyalar degistirilmedi, CSV yazilmadi, "
              "karo 512 sayimi yorumlanmadi.")
        sys.exit(1)

    kosu = kosu_bilgisi(
        bolumler=",".join(BOLUMLER),
        min_gorunur=MIN_GORUNUR,
        sayim_kipi=(
            "yalnizca sayim; karo goruntusu, etiket dosyasi ve cikti veri klasoru "
            "uretilmedi, negatif ornekleme yapilmadi"
        ),
        kaynak_script="scripts/16_adim_sabit_karo_sayimi.py",
        kullanilan_islevler=(
            "backend/core/tiling.py:karolari_hesapla, "
            "scripts/11_karo_veri_hazirla.py:bolumu_planla/gorunur_oran/kutuyu_karoya_tasi, "
            "scripts/15_kenar_kurali_yukseklik.py:hedefleri_izle"
        ),
        adim_piksel=adim,
        girdi=(
            f"{arg.veri.as_posix()} + {arg.manifest_320.as_posix()} + "
            f"{arg.log_320.as_posix()} + {arg.istatistik.as_posix()}"
        ),
        kosul_320_durumu=(
            "daha once uretilmis egitim kumesiyle capraz kontrol edildi "
            f"({arg.log_320.name})"
        ),
        kosul_512_durumu=(
            "YENI OLCUM: karo 512 / ortusme 0.53125 daha once uretilmedi; mevcut "
            "karo 512 / ortusme 0.20 manifestinin sonucu DEGILDIR"
        ),
        kapsam_notu=(
            "yalnizca egitim verisi hazirlama davranisi olculdu; recall ve model "
            "ustunlugu bu olcumde yer almaz"
        ),
    )
    cikti = csv_yaz(arg.cikti, satirlar, kosu)

    print("\n=== SAYIM ===")
    tablo_bas(satirlar, [
        "kosul", "adim_piksel", "kaynak_goruntu_sayisi", "benzersiz_hedef_sayisi",
        "planlanan_toplam_karo", "pozitif_karo", "belirsiz_karo", "negatif_aday_karo",
        "gecerli_karo_etiket_sayisi", "atlanan_hedef_ornegi_sayisi",
        "en_az_bir_belirsiz_karoya_dusen_benzersiz_hedef",
        "en_az_bir_gecerli_ornegi_olan_benzersiz_hedef",
        "tamamen_kaybolan_benzersiz_hedef", "hedef_basina_gecerli_karo_etiket",
        "belirsiz_karoya_dusen_hedef_orani",
    ])
    print(f"\nCSV: {cikti}  ({len(satirlar)} satir)")

    sonuc = sonuc_etiketi(satirlar)
    print("\n=== SONUC ===")
    print(f"Belirsiz karoya dusen hedef orani: {sonuc.get('belirsiz_orani')}")
    print(f"Hedef basina gecerli karo-etiket : {sonuc.get('hedef_basina_ornek')}")
    print(f"Etiket: {sonuc['etiket']}")
    print("Farkin model recall'ina etkisi: olculmedi.")


if __name__ == "__main__":
    main()
