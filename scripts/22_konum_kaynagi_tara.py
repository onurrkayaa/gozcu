"""Konum (GPS/koordinat) kaynaklarini tarar ve tek bir karar CSV'si uretir.

Hafta 5'in ilk karari sudur: arayuz bir goreve veya kareye konum yazabilir mi?
Bu soru tahminle degil sayimla cevaplanir. Script hicbir cikarim calistirmaz;
yalnizca metadata okur, bu yuzden veri kumesinin tamami (train + valid + test)
tek kosuda taranabilir.

Taranan kaynaklar:

1. HERIDAL goruntuleri -- her bolum icin EXIF, GPS IFD ve enlem/boylam sayimi.
2. Veritabanindaki Frame kayitlari -- alanlar dolu mu (docker uzerinden).
3. Yan dosyalar -- ucus gunlugu, konum tablosu vb. depoda var mi.
4. Dosya adlari -- addan koordinat cikarilabilir mi.

Cikti: reports/hafta5_gps_kaynak_karari.csv

CSV'de OLCUM satirlari ile KARAR satirlari ayni dosyada durur; hangisinin
hangisi oldugu `olcum_karar_ayrimi` sutunundan okunur. Karar satirlari yeni
sayim uretmez, olcum satirlarindan cikarilan politikayi yazar.
"""
import argparse
import csv
import json
import platform
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image

DEPO_KOKU = Path(__file__).resolve().parent.parent
VARSAYILAN_CIKTI = DEPO_KOKU / "reports" / "hafta5_gps_kaynak_karari.csv"

# Ucus gunlugu / konum tablosu olabilecek dosya adi kaliplari. Aranan sey
# "koordinat tasiyabilecek yan dosya"; bulunursa elle incelenir.
YAN_DOSYA_KALIPLARI = ("*.gpx", "*.kml", "*.srt", "*.csv", "*.json", "*.xml", "*.log")

# Dosya adindan koordinat cikarma denemesi icin: ondalik derece gibi duran
# sayi ciftleri. HERIDAL adlari "train_BLA_0003_JPG.rf.<hash>.jpg" biciminde,
# yani bu kalibin eslesmemesi BEKLENEN sonuctur; sayim yine de yapilir ki
# "bakmadik" denemesin.
KOORDINAT_KALIBI = re.compile(r"(-?\d{1,3}\.\d{4,})[_,\s]+(-?\d{1,3}\.\d{4,})")

SUTUNLAR = [
    "incelenen_kaynak",
    "bolum",
    "incelenen_goruntu_sayisi",
    "exif_bulunan_goruntu",
    "gps_ifd_bulunan_goruntu",
    "enlem_boylam_bulunan_goruntu",
    "koordinat_dogrulanabilir_mi",
    "kaynak_turu",
    "guven_duzeyi",
    "kullanim_karari",
    "gerekce",
    "olcum_karar_ayrimi",
    "uretici_script",
    "kosu_komut",
    "kosu_tarih",
    "kosu_surum_python",
    "kosu_surum_pillow",
    "kosu_platform",
    "kosu_veri_kumesi",
    "kosu_kapsam_notu",
]


def goruntu_dizinini_bul(veri_koku, bolum):
    """Bolum goruntu dizinini arayarak bulur; yolu koda sabitlemez.

    Tek aday bulunmasi beklenir. Sifir veya birden fazla aday cikarsa hata
    verilir -- yanlis dizini sessizce taramaktansa durmak yeglenir.
    """
    adaylar = sorted(
        {
            yol
            for kalip in (f"{bolum}/images", f"*/{bolum}/images")
            for yol in veri_koku.glob(kalip)
            if yol.is_dir()
        }
    )
    if len(adaylar) != 1:
        raise SystemExit(
            f"'{bolum}' bolumu icin tek goruntu dizini bulunamadi. "
            f"Adaylar: {[str(a) for a in adaylar]}"
        )
    return adaylar[0]


def goruntuleri_listele(dizin):
    return sorted(
        yol
        for yol in dizin.iterdir()
        if yol.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff")
    )


def tek_goruntuyu_incele(yol):
    """(exif_var, gps_ifd_var, enlem_boylam_var) doner.

    Okuma hatasi olan dosya "EXIF yok" sayilmaz; ayri sayilir ki bozuk dosya
    ile EXIF'i silinmis dosya birbirine karismasin.
    """
    try:
        with Image.open(yol) as goruntu:
            exif = goruntu.getexif()
    except Exception:
        return None

    if not exif:
        return (False, False, False)

    try:
        gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:
        gps = {}

    enlem_boylam = bool(
        gps
        and gps.get(ExifTags.GPS.GPSLatitude)
        and gps.get(ExifTags.GPS.GPSLongitude)
    )
    return (True, bool(gps), enlem_boylam)


def bolumu_tara(dizin, sinir=None):
    goruntuler = goruntuleri_listele(dizin)
    if sinir is not None:
        goruntuler = goruntuler[:sinir]

    sayim = {
        "toplam": len(goruntuler),
        "exif": 0,
        "gps": 0,
        "enlem_boylam": 0,
        "okunamadi": 0,
        "addan_koordinat": 0,
    }
    for yol in goruntuler:
        if KOORDINAT_KALIBI.search(yol.name):
            sayim["addan_koordinat"] += 1
        sonuc = tek_goruntuyu_incele(yol)
        if sonuc is None:
            sayim["okunamadi"] += 1
            continue
        exif_var, gps_var, enlem_boylam_var = sonuc
        sayim["exif"] += int(exif_var)
        sayim["gps"] += int(gps_var)
        sayim["enlem_boylam"] += int(enlem_boylam_var)
    return sayim


VERITABANI_SORGUSU = """
import json
from core.models import Frame
print("FRAME_OZETI=" + json.dumps({
    "toplam": Frame.objects.count(),
    "enlem_dolu": Frame.objects.filter(latitude__isnull=False).count(),
    "boylam_dolu": Frame.objects.filter(longitude__isnull=False).count(),
    "irtifa_dolu": Frame.objects.filter(altitude_m__isnull=False).count(),
    "cekim_zamani_dolu": Frame.objects.filter(captured_at__isnull=False).count(),
}))
"""


def veritabanini_tara(servis):
    """Frame kayitlarindaki konum alanlarini docker uzerinden sayar.

    Veritabani portu disari acilmadigi icin sorgu konteyner icinde calisir.
    Docker yoksa None doner ve CSV'ye "olculemedi" yazilir -- sifir yazilmaz,
    cunku olculmemis olmak ile bos olmak ayni sey degildir.
    """
    komut = [
        "docker", "compose", "exec", "-T", servis,
        "python", "manage.py", "shell", "-c", VERITABANI_SORGUSU,
    ]
    try:
        cikti = subprocess.run(
            komut, cwd=DEPO_KOKU, capture_output=True, text=True, timeout=120
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if cikti.returncode != 0:
        return None
    for satir in cikti.stdout.splitlines():
        if satir.startswith("FRAME_OZETI="):
            return json.loads(satir[len("FRAME_OZETI="):])
    return None


def yan_dosyalari_ara(veri_koku):
    """Koordinat tasiyabilecek yan dosyalari sayar (goruntu ve etiket disi)."""
    bulunan = []
    for kalip in YAN_DOSYA_KALIPLARI:
        for yol in veri_koku.rglob(kalip):
            if yol.is_file():
                bulunan.append(yol.relative_to(DEPO_KOKU).as_posix())
    return sorted(bulunan)


def pillow_surumu():
    try:
        from PIL import __version__

        return __version__
    except Exception:
        return "bilinmiyor"


def main():
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument(
        "--veri-koku",
        default=str(DEPO_KOKU / "data" / "heridal"),
        help="HERIDAL veri kumesi koku.",
    )
    ayristirici.add_argument(
        "--bolumler",
        nargs="+",
        default=["train", "valid", "test"],
        help="Taranacak bolumler. Varsayilan: tamami.",
    )
    ayristirici.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Bolum basina en fazla kac goruntu taransin (varsayilan: tamami).",
    )
    ayristirici.add_argument(
        "--docker-servis",
        default="web",
        help="Frame sayimi icin kullanilacak docker compose servisi.",
    )
    ayristirici.add_argument(
        "--veritabani-atla",
        action="store_true",
        help="Veritabani sayimini atla.",
    )
    ayristirici.add_argument("--cikti", default=str(VARSAYILAN_CIKTI))
    argumanlar = ayristirici.parse_args()

    veri_koku = Path(argumanlar.veri_koku).resolve()
    if not veri_koku.is_dir():
        raise SystemExit(f"Veri koku bulunamadi: {veri_koku}")

    kosu = {
        "uretici_script": "scripts/22_konum_kaynagi_tara.py",
        "kosu_komut": " ".join(
            ["python", "scripts/22_konum_kaynagi_tara.py"] + sys.argv[1:]
        ),
        "kosu_tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kosu_surum_python": platform.python_version(),
        "kosu_surum_pillow": pillow_surumu(),
        "kosu_platform": f"{platform.system()} {platform.machine()}",
        "kosu_veri_kumesi": veri_koku.relative_to(DEPO_KOKU).as_posix()
        if veri_koku.is_relative_to(DEPO_KOKU)
        else str(veri_koku),
        "kosu_kapsam_notu": (
            "yalnizca metadata okundu; hicbir cikarim calistirilmadi, "
            "model yuklenmedi"
        ),
    }

    satirlar = []
    toplam = {"toplam": 0, "exif": 0, "gps": 0, "enlem_boylam": 0,
              "okunamadi": 0, "addan_koordinat": 0}

    for bolum in argumanlar.bolumler:
        dizin = goruntu_dizinini_bul(veri_koku, bolum)
        sayim = bolumu_tara(dizin, argumanlar.limit)
        for anahtar in toplam:
            toplam[anahtar] += sayim[anahtar]
        print(
            f"{bolum}: {sayim['toplam']} goruntu, EXIF {sayim['exif']}, "
            f"GPS {sayim['gps']}, enlem/boylam {sayim['enlem_boylam']}"
        )
        satirlar.append({
            **kosu,
            "incelenen_kaynak": "HERIDAL goruntu dosyasi (EXIF)",
            "bolum": bolum,
            "incelenen_goruntu_sayisi": sayim["toplam"],
            "exif_bulunan_goruntu": sayim["exif"],
            "gps_ifd_bulunan_goruntu": sayim["gps"],
            "enlem_boylam_bulunan_goruntu": sayim["enlem_boylam"],
            "koordinat_dogrulanabilir_mi": "hayir",
            "kaynak_turu": "EXIF GPS",
            "guven_duzeyi": "yok",
            "kullanim_karari": "kullanilamaz",
            "gerekce": (
                f"{sayim['toplam']} goruntunun {sayim['exif']} tanesinde EXIF blogu "
                f"var, {sayim['enlem_boylam']} tanesinde enlem/boylam var. "
                f"Okunamayan dosya: {sayim['okunamadi']}."
            ),
            "olcum_karar_ayrimi": "olcum",
        })

    satirlar.append({
        **kosu,
        "incelenen_kaynak": "HERIDAL goruntu dosyasi (EXIF)",
        "bolum": "TOPLAM",
        "incelenen_goruntu_sayisi": toplam["toplam"],
        "exif_bulunan_goruntu": toplam["exif"],
        "gps_ifd_bulunan_goruntu": toplam["gps"],
        "enlem_boylam_bulunan_goruntu": toplam["enlem_boylam"],
        "koordinat_dogrulanabilir_mi": "hayir",
        "kaynak_turu": "EXIF GPS",
        "guven_duzeyi": "yok",
        "kullanim_karari": "kullanilamaz",
        "gerekce": (
            "Veri kumesi Roboflow uzerinden yeniden disa aktarildigi icin EXIF "
            "bloklari tamamen silinmis. Kaynak HERIDAL yayininda GPS olsa bile "
            "elimizdeki kopyada yok."
        ),
        "olcum_karar_ayrimi": "olcum",
    })

    # --- Dosya adindan koordinat -------------------------------------------
    satirlar.append({
        **kosu,
        "incelenen_kaynak": "Goruntu dosya adi",
        "bolum": "TOPLAM",
        "incelenen_goruntu_sayisi": toplam["toplam"],
        "exif_bulunan_goruntu": "",
        "gps_ifd_bulunan_goruntu": "",
        "enlem_boylam_bulunan_goruntu": toplam["addan_koordinat"],
        "koordinat_dogrulanabilir_mi": "hayir",
        "kaynak_turu": "dosya adi",
        "guven_duzeyi": "yok",
        "kullanim_karari": "kullanilamaz",
        "gerekce": (
            "Adlar 'train_<ONEK>_<sira>_JPG.rf.<hash>.jpg' biciminde; onek "
            "kaynak veri kumesini gosterir, konum degil. Ondalik derece kalibina "
            f"uyan ad sayisi {toplam['addan_koordinat']}. Sira numarasindan "
            "enlem/boylam turetmek uydurma olur."
        ),
        "olcum_karar_ayrimi": "olcum",
    })

    # --- Yan dosyalar -------------------------------------------------------
    yan_dosyalar = yan_dosyalari_ara(veri_koku)
    satirlar.append({
        **kosu,
        "incelenen_kaynak": "Yan dosya (ucus gunlugu, gpx/kml/srt/csv/json)",
        "bolum": "TOPLAM",
        "incelenen_goruntu_sayisi": "",
        "exif_bulunan_goruntu": "",
        "gps_ifd_bulunan_goruntu": "",
        "enlem_boylam_bulunan_goruntu": 0,
        "koordinat_dogrulanabilir_mi": "hayir",
        "kaynak_turu": "ucus gunlugu / yan dosya",
        "guven_duzeyi": "yok",
        "kullanim_karari": "kullanilamaz",
        "gerekce": (
            "Veri kumesi kokunde koordinat tasiyan yan dosya yok. Bulunanlar: "
            + (", ".join(yan_dosyalar) if yan_dosyalar else "hicbiri")
            + ". Bunlar sinif/bolum tanimi icerir, konum icermez."
        ),
        "olcum_karar_ayrimi": "olcum",
    })

    # --- Veritabanindaki Frame kayitlari ------------------------------------
    if argumanlar.veritabani_atla:
        frame_ozeti = None
        frame_notu = "atlandi (--veritabani-atla)"
    else:
        frame_ozeti = veritabanini_tara(argumanlar.docker_servis)
        frame_notu = "" if frame_ozeti else "olculemedi (docker/servis erisilemedi)"

    if frame_ozeti:
        gerekce = (
            f"{frame_ozeti['toplam']} Frame kaydinin {frame_ozeti['enlem_dolu']} "
            f"tanesinde latitude, {frame_ozeti['boylam_dolu']} tanesinde longitude, "
            f"{frame_ozeti['irtifa_dolu']} tanesinde altitude_m, "
            f"{frame_ozeti['cekim_zamani_dolu']} tanesinde captured_at dolu. "
            "Alanlar modelde var ve alim sirasinda EXIF'ten doldurulmaya "
            "calisiliyor; kaynakta EXIF olmadigi icin bos kaliyorlar."
        )
        satirlar.append({
            **kosu,
            "incelenen_kaynak": "Veritabani Frame kaydi (latitude/longitude)",
            "bolum": "yerel veritabani",
            "incelenen_goruntu_sayisi": frame_ozeti["toplam"],
            "exif_bulunan_goruntu": frame_ozeti["cekim_zamani_dolu"],
            "gps_ifd_bulunan_goruntu": "",
            "enlem_boylam_bulunan_goruntu": min(
                frame_ozeti["enlem_dolu"], frame_ozeti["boylam_dolu"]
            ),
            "koordinat_dogrulanabilir_mi": "hayir",
            "kaynak_turu": "Frame.latitude / Frame.longitude",
            "guven_duzeyi": "yok",
            "kullanim_karari": "kullanilamaz",
            "gerekce": gerekce,
            "olcum_karar_ayrimi": "olcum",
        })
    else:
        satirlar.append({
            **kosu,
            "incelenen_kaynak": "Veritabani Frame kaydi (latitude/longitude)",
            "bolum": "yerel veritabani",
            "incelenen_goruntu_sayisi": "",
            "exif_bulunan_goruntu": "",
            "gps_ifd_bulunan_goruntu": "",
            "enlem_boylam_bulunan_goruntu": "",
            "koordinat_dogrulanabilir_mi": "olculemedi",
            "kaynak_turu": "Frame.latitude / Frame.longitude",
            "guven_duzeyi": "olculemedi",
            "kullanim_karari": "olculemedi",
            "gerekce": frame_notu,
            "olcum_karar_ayrimi": "olcum",
        })

    # --- KARAR satirlari ----------------------------------------------------
    kararlar = [
        (
            "POLITIKA: arayuzde konum gosterimi",
            "Hafta 5",
            "gosterilmez",
            "Hicbir kaynakta dogrulanabilir koordinat yok. Arayuz gorev ve kare "
            "ayrintisinda 'Konum bilgisi mevcut degil' gosterir; harita, pin veya "
            "koordinat metni uretmez.",
        ),
        (
            "POLITIKA: turetilmis koordinat",
            "Hafta 5",
            "yasak",
            "Dosya sirasindan, karo satir/sutunundan veya goruntu pikselinden "
            "enlem/boylam turetilmez. Bu degerler olcum degil uydurma olur ve "
            "arama ekibini yanlis noktaya yonlendirir.",
        ),
        (
            "POLITIKA: demo/sentetik koordinat",
            "Hafta 6",
            "yalnizca acik etiketle",
            "Hafta 6'da harita gosterimi gerekirse kullanilacak koordinat "
            "'Demo konumu -- gercek GPS degildir' etiketiyle hem veride hem "
            "arayuzde isaretlenir; gercek EXIF veya gercek ucus rotasi gibi "
            "sunulmaz.",
        ),
        (
            "ONCELIK 1: dogrulanmis EXIF GPS",
            "gelecek",
            "tercih edilen",
            "EXIF'i silinmemis ozgun goruntu saglanirsa ilk tercih budur; "
            "alim hattinda okuma kodu (core/services.extract_exif) zaten hazir.",
        ),
        (
            "ONCELIK 2: ucus gunlugu + zaman damgasi eslestirmesi",
            "gelecek",
            "kosullu",
            "Drone ucus gunlugu ve captured_at birlikte varsa eslestirme "
            "yapilabilir; eslestirme toleransi ve basarisiz eslesme sayisi "
            "kaydedilmelidir.",
        ),
        (
            "ONCELIK 3: kullanicinin acikca verdigi gorev/kare konumu",
            "gelecek",
            "kosullu",
            "Operator konumu elle girerse kaynak 'operator beyani' olarak "
            "saklanir; olculmus GPS ile ayni sutunda ayrimsiz durmaz.",
        ),
        (
            "ONCELIK 4: acikca etiketlenmis demo/sentetik koordinat",
            "gelecek",
            "yalnizca demo",
            "Yalnizca gosterim amacli; gercek gorev karari icin kullanilmaz.",
        ),
        (
            "ONCELIK 5: konum yok",
            "Hafta 5 gecerli durumu",
            "gecerli",
            "Su anki durum. Konum yoklugu bir hata degil, kaydedilmis bir "
            "olgudur ve arayuzde acikca soylenir.",
        ),
        (
            "GELECEK ALAN NOTU: koordinat kaynagi (provenance)",
            "Hafta 6",
            "gerekli",
            "Koordinat saklanmaya baslandiginda degerin yaninda kaynagi da "
            "saklanmalidir (exif / ucus_gunlugu / operator / demo). Kaynak "
            "bilgisi olmadan demo ile gercek koordinat ayirt edilemez. Bu alan "
            "Hafta 5'te EKLENMEDI; yalnizca not edildi.",
        ),
    ]
    for kaynak, bolum, karar, gerekce in kararlar:
        satirlar.append({
            **kosu,
            "incelenen_kaynak": kaynak,
            "bolum": bolum,
            "incelenen_goruntu_sayisi": "",
            "exif_bulunan_goruntu": "",
            "gps_ifd_bulunan_goruntu": "",
            "enlem_boylam_bulunan_goruntu": "",
            "koordinat_dogrulanabilir_mi": "",
            "kaynak_turu": "",
            "guven_duzeyi": "",
            "kullanim_karari": karar,
            "gerekce": gerekce,
            "olcum_karar_ayrimi": "karar",
        })

    cikti_yolu = Path(argumanlar.cikti)
    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    with open(cikti_yolu, "w", newline="", encoding="utf-8") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=SUTUNLAR)
        yazici.writeheader()
        for satir in satirlar:
            yazici.writerow({sutun: satir.get(sutun, "") for sutun in SUTUNLAR})

    print(f"\nToplam {toplam['toplam']} goruntu tarandi.")
    print(f"EXIF bulunan: {toplam['exif']}, enlem/boylam bulunan: {toplam['enlem_boylam']}")
    print(f"Yazildi: {cikti_yolu.relative_to(DEPO_KOKU)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
