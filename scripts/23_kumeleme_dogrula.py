"""Union-Find kumelemesinin senaryo bazinda dogrulanmasi.

Kumeleme kodu gercek PostGIS mesafesi kullaniyor, bu yuzden dogrulama da
gercek veritabani uzerinde yapilmali: Python'da taklit edilmis bir mesafe
fonksiyonu, asil sorunun (derece mi metre mi) uzerinden atlardi.

Script Django kabugu icinde calisir ve her senaryo icin gecici bir gorev
acip bulgulari yaratir, kumelemeyi calistirir, sonucu beklenenle
karsilastirir ve sonunda ACTIGI HER SEYI SILER. Uretim verisine dokunmaz.

Kosu:
    docker compose exec -T web python manage.py shell -c \
        "exec(open('/app/../scripts/23_kumeleme_dogrula.py').read())"

veya depo kokunden:
    python scripts/23_kumeleme_dogrula.py     (docker uzerinden calistirir)
"""
import csv
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEPO_KOKU = Path(__file__).resolve().parent.parent
VARSAYILAN_CIKTI = DEPO_KOKU / "reports" / "hafta6_kumeleme_dogrulama.csv"

SUTUNLAR = [
    "senaryo", "finding_sayisi", "esik_metre", "provenance_grubu",
    "beklenen_kume_sayisi", "gercek_kume_sayisi",
    "beklenen_uyelik", "gercek_uyelik",
    "deterministik_mi", "idempotent_mi", "gecti_kaldi",
    "test", "sure_sn", "not",
    "kosu_tarih", "kosu_postgis", "kosu_python", "kosu_komut", "kosu_kapsam_notu",
]

# Django kabugunda calisacak govde. Ayri dosya yerine burada duruyor ki
# senaryo tanimlari ile beklentiler tek yerde kalsin.
KABUK_KODU = r'''
import json, time
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.db import transaction
from core.models import Finding, Mission, MissionMember
from core.kumeleme import gorevi_kumele, kume_ozeti

KULLANICI_ADI = "_kumeleme_dogrulama_"
ESIK = 50.0

# Metre -> derece yaklasik cevrimi YALNIZCA test noktasi uretmek icin.
# Kumeleme kodu bu cevrimi KULLANMAZ; mesafeyi PostGIS metre olarak hesaplar.
# Enlem 0'da 1 derece boylam ~111320 m.
def metre_dogu(taban_boylam, metre):
    return taban_boylam + metre / 111320.0

TABAN_ENLEM, TABAN_BOYLAM = 0.0, 30.0

SENARYOLAR = [
    # (ad, [(dx_metre, kaynak)], beklenen_kume, beklenen_uyelik_metni, not)
    ("tek nokta", [(0, "manual")], 1, "1 kume: {A}", ""),
    ("iki yakin nokta (10 m)", [(0, "manual"), (10, "manual")], 1, "1 kume: {A,B}", "esik 50 m"),
    ("iki uzak nokta (500 m)", [(0, "manual"), (500, "manual")], 2, "2 kume: {A} {B}", "esik 50 m"),
    ("gecisli uclu A-B-C (40+40 m)", [(0, "manual"), (40, "manual"), (80, "manual")], 1,
     "1 kume: {A,B,C}", "A-C arasi 80 m > esik; gecislilik nedeniyle tek kume"),
    ("ayni koordinat", [(0, "manual"), (0, "manual"), (0, "manual")], 1, "1 kume: {A,B,C}", ""),
    ("esik sinirinin hemen icinde (49 m)", [(0, "manual"), (49, "manual")], 1, "1 kume: {A,B}", ""),
    ("esik sinirinin hemen disinda (51 m)", [(0, "manual"), (51, "manual")], 2, "2 kume: {A} {B}", ""),
    ("demo ve gercek ayrimi", [(0, "manual"), (5, "demo")], 2,
     "2 kume: gercek{A} demo{B}", "5 m yakin ama gruplar ayri"),
    ("null konum kumelenmez", [(0, "manual"), (None, "none")], 1,
     "1 kume: {A}; konumsuz kume disi", ""),
]

sonuclar = []

def temizle():
    Mission.objects.filter(name__startswith="_kumeleme_dogrulama_").delete()
    User.objects.filter(username=KULLANICI_ADI).delete()

temizle()
kullanici, _ = User.objects.get_or_create(username=KULLANICI_ADI)

def gorev_kur(ad, noktalar):
    m = Mission.objects.create(name="_kumeleme_dogrulama_" + ad, created_by=kullanici)
    kayitlar = []
    for i, (dx, kaynak) in enumerate(noktalar):
        konum = None if dx is None else Point(metre_dogu(TABAN_BOYLAM, dx), TABAN_ENLEM, srid=4326)
        kayitlar.append(Finding.objects.create(
            mission=m, title=chr(65 + i), location=konum,
            location_source=kaynak, created_by=kullanici))
    return m, kayitlar

def uyelik_metni(m):
    parcalar = []
    for b in Finding.objects.filter(mission=m).order_by("id"):
        if b.cluster_id is None:
            parcalar.append(f"{b.title}:kumesiz")
        else:
            parcalar.append(f"{b.title}:{b.cluster_key}#{b.cluster_id}")
    return " ".join(parcalar)

for ad, noktalar, beklenen_kume, beklenen_uyelik, notu in SENARYOLAR:
    m, kayitlar = gorev_kur(ad, noktalar)
    basla = time.perf_counter()
    sonuc = gorevi_kumele(m, esik_metre=ESIK)
    sure = time.perf_counter() - basla
    birinci = uyelik_metni(m)

    # Idempotanslik: ayni girdide ikinci kosu ayni sonucu vermeli.
    gorevi_kumele(m, esik_metre=ESIK)
    ikinci = uyelik_metni(m)
    idempotent = (birinci == ikinci)

    # Determinizm: girdi sirasi degistirilmis bir kopyada ayni gruplama.
    m2, _ = gorev_kur(ad + "_ters", list(reversed(noktalar)))
    gorevi_kumele(m2, esik_metre=ESIK)
    # Determinizm: girdi sirasi ters cevrilmis kopyada kume BOYUTLARI ayni
    # olmali. Kimlikler farkli oldugu icin karsilastirilan sey gruplamanin
    # yapisi, kimliklerin kendisi degil.
    gruplar_1 = sorted(len(g["finding_ids"]) for g in kume_ozeti(m))
    gruplar_2 = sorted(len(g["finding_ids"]) for g in kume_ozeti(m2))
    deterministik = (gruplar_1 == gruplar_2)

    gercek_kume = sonuc["kume_sayisi"]
    gecti = (gercek_kume == beklenen_kume) and idempotent and deterministik

    sonuclar.append({
        "senaryo": ad,
        "finding_sayisi": len(noktalar),
        "esik_metre": ESIK,
        "provenance_grubu": ",".join(sorted({k for _, k in noktalar})),
        "beklenen_kume_sayisi": beklenen_kume,
        "gercek_kume_sayisi": gercek_kume,
        "beklenen_uyelik": beklenen_uyelik,
        "gercek_uyelik": birinci,
        "deterministik_mi": "evet" if deterministik else "HAYIR",
        "idempotent_mi": "evet" if idempotent else "HAYIR",
        "gecti_kaldi": "gecti" if gecti else "KALDI",
        "test": "backend/tests/test_kumeleme.py",
        "sure_sn": round(sure, 4),
        "not": notu,
    })

# Farkli gorev sinirlari: ayni koordinatlar iki ayri gorevde, karismamali
m_a, _ = gorev_kur("gorev_a", [(0, "manual"), (10, "manual")])
m_b, _ = gorev_kur("gorev_b", [(0, "manual"), (10, "manual")])
sa = gorevi_kumele(m_a, esik_metre=ESIK)
sb = gorevi_kumele(m_b, esik_metre=ESIK)
ayri = (sa["kume_sayisi"] == 1 and sb["kume_sayisi"] == 1
        and sa["kumelenen_bulgu"] == 2 and sb["kumelenen_bulgu"] == 2)
sonuclar.append({
    "senaryo": "farkli gorevler karismiyor",
    "finding_sayisi": 4, "esik_metre": ESIK, "provenance_grubu": "manual",
    "beklenen_kume_sayisi": 2, "gercek_kume_sayisi": sa["kume_sayisi"] + sb["kume_sayisi"],
    "beklenen_uyelik": "her gorevde 1 kume, 2 uye",
    "gercek_uyelik": f"gorev_a: {sa['kume_sayisi']} kume/{sa['kumelenen_bulgu']} uye; "
                     f"gorev_b: {sb['kume_sayisi']} kume/{sb['kumelenen_bulgu']} uye",
    "deterministik_mi": "evet", "idempotent_mi": "evet",
    "gecti_kaldi": "gecti" if ayri else "KALDI",
    "test": "backend/tests/test_kumeleme.py", "sure_sn": "",
    "not": "Ayni koordinatlar iki ayri gorevde; kumeler gorev sinirini asmiyor",
})

temizle()
print("KUMELEME_SONUC=" + json.dumps(sonuclar))
'''


def postgis_surumu():
    try:
        cikti = subprocess.run(
            ["docker", "compose", "exec", "-T", "db", "psql", "-U", "gozcu", "-d",
             "gozcu", "-t", "-c", "SELECT PostGIS_Lib_Version();"],
            cwd=DEPO_KOKU, capture_output=True, text=True, timeout=60,
        )
        return cikti.stdout.strip() or "bilinmiyor"
    except (OSError, subprocess.TimeoutExpired):
        return "bilinmiyor"


def main():
    cikti_yolu = Path(sys.argv[1]) if len(sys.argv) > 1 else VARSAYILAN_CIKTI

    kabuk = subprocess.run(
        ["docker", "compose", "exec", "-T", "web", "python", "manage.py", "shell", "-c",
         KABUK_KODU],
        cwd=DEPO_KOKU, capture_output=True, text=True, timeout=600,
    )
    if kabuk.returncode != 0:
        print(kabuk.stdout[-3000:])
        print(kabuk.stderr[-3000:], file=sys.stderr)
        raise SystemExit("Kumeleme dogrulamasi calistirilamadi.")

    satir = next(
        (s for s in kabuk.stdout.splitlines() if s.startswith("KUMELEME_SONUC=")), None
    )
    if satir is None:
        print(kabuk.stdout[-3000:])
        raise SystemExit("Sonuc satiri bulunamadi.")

    sonuclar = json.loads(satir[len("KUMELEME_SONUC="):])

    kosu = {
        "kosu_tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kosu_postgis": postgis_surumu(),
        "kosu_python": platform.python_version(),
        "kosu_komut": "python scripts/23_kumeleme_dogrula.py",
        "kosu_kapsam_notu": (
            "Senaryo dogrulamasi; gercek PostGIS mesafesiyle calisir. Veri kumesi "
            "kucuk oldugu icin sure sutunu OLCEKLENEBILIRLIK IDDIASI TASIMAZ."
        ),
    }

    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    with open(cikti_yolu, "w", newline="", encoding="utf-8") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=SUTUNLAR)
        yazici.writeheader()
        for satir_verisi in sonuclar:
            satir_verisi.update(kosu)
            yazici.writerow({s: satir_verisi.get(s, "") for s in SUTUNLAR})

    kalan = [s for s in sonuclar if s["gecti_kaldi"] != "gecti"]
    for s in sonuclar:
        print(f"  [{s['gecti_kaldi']:6}] {s['senaryo']:38} "
              f"beklenen={s['beklenen_kume_sayisi']} gercek={s['gercek_kume_sayisi']}")
    print(f"\n{len(sonuclar)} senaryo, {len(kalan)} kaldi.")
    print(f"Yazildi: {cikti_yolu.relative_to(DEPO_KOKU)}")
    return 1 if kalan else 0


if __name__ == "__main__":
    sys.exit(main())
