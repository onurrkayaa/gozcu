"""Rol/islem yetki matrisini GERCEK HTTP kodlarindan uretir.

Matris elle yazilmaz: her islem, dort kullanici sinifiyla (owner, operator,
viewer, uye olmayan) gercekten cagrilir ve donen kod kaydedilir. Beklenen kod
kaynakta tanimlidir; gercek kod ile karsilastirilir. Boylece CSV bir niyet
beyani degil, calisan sistemin olcumu olur.

Script gecici bir gorev ve dort gecici kullanici acar, olcumu yapar ve
ACTIGI HER SEYI SILER. Uretim verisine dokunmaz.

Kosu (depo kokunden):
    python scripts/24_yetki_matrisi.py
"""
import csv
import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DEPO_KOKU = Path(__file__).resolve().parent.parent
VARSAYILAN_CIKTI = DEPO_KOKU / "reports" / "hafta6_yetki_matrisi.csv"

SUTUNLAR = [
    "islem", "owner", "operator", "viewer", "uye_olmayan",
    "beklenen_http", "gercek_http", "gecti_kaldi", "test", "not",
    "kosu_tarih", "kosu_python", "kosu_komut", "kosu_kapsam_notu",
]

KABUK_KODU = r'''
import json
from django.conf import settings

# Django test istemcisi "testserver" host'unu kullanir; kabuk icinde
# ALLOWED_HOSTS bunu icermedigi icin her istek 400 (DisallowedHost) donerdi ve
# matris yetkiyi degil host reddini olcerdi. Yalnizca bu surec icin genisletilir.
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ["testserver"]

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient
from core.models import Detection, Finding, Frame, InferenceRun, Mission, MissionMember, ModelVersion
from core.services import ingest_frame
import io
from PIL import Image

ONEK = "_yetki_matrisi_"

def temizle():
    Mission.objects.filter(name__startswith=ONEK).delete()
    User.objects.filter(username__startswith=ONEK).delete()

temizle()

def kullanici(ad):
    return User.objects.create_user(username=ONEK + ad, password="gecici-olcum-parolasi")

sahip = kullanici("owner")
oper = kullanici("operator")
izle = kullanici("viewer")
yaban = kullanici("yabanci")

gorev = Mission.objects.create(name=ONEK + "gorev", created_by=sahip)
MissionMember.objects.create(mission=gorev, user=oper, role="operator")
MissionMember.objects.create(mission=gorev, user=izle, role="viewer")

def goruntu(ad):
    tampon = io.BytesIO()
    Image.new("RGB", (64, 48), (20, 90, 160)).save(tampon, format="JPEG")
    tampon.seek(0)
    tampon.name = ad
    return tampon

for i in range(2):
    tampon = io.BytesIO()
    Image.new("RGB", (64, 48), (i * 50, 90, 160)).save(tampon, format="JPEG")
    from django.core.files.uploadedfile import SimpleUploadedFile
    ingest_frame(gorev, SimpleUploadedFile(f"m{i}.jpg", tampon.getvalue(), content_type="image/jpeg"))

kare = Frame.objects.filter(mission=gorev).first()
model = ModelVersion.objects.get(name="fake-v0")

# Tespit uretmek icin kisa bir kosu (sahte dedektor, kuyruk yok).
from django.test import override_settings
from core.tasks import process_frame
kosu = InferenceRun.objects.create(
    mission=gorev, model_version=model, conf_threshold=0.0, iou_threshold=0.45,
    tile_size=512, overlap_ratio=0.2, status="done", frames_total=2)
for k in Frame.objects.filter(mission=gorev):
    process_frame.apply(args=(kosu.id, k.id)).get()
tespit = Detection.objects.filter(inference_run=kosu).first()

bulgu = Finding.objects.create(mission=gorev, location_source="none", created_by=sahip)

# Uye ekleme islemi icin her rolun deneyecegi ayri bir aday kullanici.
for _rol in ("owner", "operator", "viewer", "uye_olmayan"):
    User.objects.create_user(username=ONEK + "aday_" + _rol, password="gecici-olcum-parolasi")
uyelik_izleyici = MissionMember.objects.get(mission=gorev, user=izle)

def istemci(u):
    c = APIClient()
    c.force_authenticate(user=u)
    return c

ROLLER = [("owner", sahip), ("operator", oper), ("viewer", izle), ("uye_olmayan", yaban)]

def gorsel_dosya():
    tampon = io.BytesIO()
    Image.new("RGB", (48, 32), (7, 7, 7)).save(tampon, format="JPEG")
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile("yetki.jpg", tampon.getvalue(), content_type="image/jpeg")

# (islem adi, cagri fonksiyonu, beklenen kodlar, test dosyasi, not)
def ISLEMLER():
    return [
      ("Mission listeleme",
       lambda c, r: c.get(reverse("mission-list")),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":200},
       "test_uyelik.py::test_uye_olmayan_gorevi_listede_gormez",
       "Uye olmayan da 200 alir ama listesi BOS doner"),
      ("Mission goruntuleme",
       lambda c, r: c.get(reverse("mission-detail", args=[gorev.id])),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_gorev_ayrintisi_matrisi", ""),
      ("Uye listeleme",
       lambda c, r: c.get(reverse("mission-members", args=[gorev.id])),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_uye_listesi_matrisi", ""),
      ("Uye ekleme",
       lambda c, r: c.post(reverse("mission-members", args=[gorev.id]),
                           {"username": ONEK + "aday_" + r, "role":"viewer"}, format="json"),
       {"owner":201,"operator":403,"viewer":403,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_uye_ekleme_matrisi", "Her rol icin ayri aday kullanici"),
      ("Rol degistirme",
       lambda c, r: c.patch(reverse("mission-member-detail", args=[gorev.id, uyelik_izleyici.id]),
                            {"role":"viewer"}, format="json"),
       {"owner":200,"operator":403,"viewer":403,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_rol_degistirme_matrisi", ""),
      ("Uye cikarma (son owner)",
       lambda c, r: c.delete(reverse("mission-member-detail", args=[gorev.id,
                             MissionMember.objects.get(mission=gorev, user=sahip).id])),
       {"owner":400,"operator":403,"viewer":403,"uye_olmayan":404},
       "test_uyelik.py::test_son_owner_cikarilamaz",
       "owner icin 400: son sahip korumasi devrede, yetki degil kural engeli"),
      ("Frame listeleme",
       lambda c, r: c.get(reverse("mission-frames", args=[gorev.id])),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_kare_listesi_matrisi", ""),
      ("Frame ekleme",
       lambda c, r: c.post(reverse("mission-frames", args=[gorev.id]), {"images": gorsel_dosya()}),
       {"owner":201,"operator":201,"viewer":403,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_kare_ekleme_matrisi", ""),
      ("Frame goruntu dosyasi",
       lambda c, r: c.get(reverse("frame-image", args=[kare.id])),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_kare_goruntusu_matrisi", ""),
      ("Run listeleme",
       lambda c, r: c.get(reverse("mission-runs", args=[gorev.id])),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_kosu_listesi_matrisi", ""),
      ("Run goruntuleme",
       lambda c, r: c.get(reverse("run-detail", args=[kosu.id])),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":404},
       "test_runs.py::test_baskasinin_kosusunu_gormek_404", ""),
      ("Detection listeleme",
       lambda c, r: c.get(reverse("run-detections", args=[kosu.id])),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_tespit_listesi_matrisi", ""),
      ("Review okuma",
       lambda c, r: c.get(reverse("detection-reviews", args=[tespit.id])),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":404},
       "test_inceleme.py::test_viewer_incelemeleri_okuyabilir", ""),
      ("Review yazma",
       lambda c, r: c.put(reverse("detection-reviews", args=[tespit.id]),
                          {"decision":"accepted"}, format="json"),
       {"owner":201,"operator":201,"viewer":403,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_inceleme_yazma_matrisi",
       "Her inceleyen KENDI kaydini actigi icin ikisi de 201; biri digerini ezmiyor"),
      ("Finding okuma",
       lambda c, r: c.get(reverse("mission-findings", args=[gorev.id])),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":404},
       "test_bulgu.py::test_viewer_bulgulari_okuyabilir", ""),
      ("Finding yazma",
       lambda c, r: c.post(reverse("mission-findings", args=[gorev.id]),
                           {"location_source":"none","title":r}, format="json"),
       {"owner":201,"operator":201,"viewer":403,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_bulgu_olusturma_matrisi", ""),
      ("Kumeleme calistirma",
       lambda c, r: c.post(reverse("mission-clusters", args=[gorev.id]), {}, format="json"),
       {"owner":200,"operator":200,"viewer":403,"uye_olmayan":404},
       "test_yetki_matrisi.py::test_kumeleme_calistirma_matrisi", ""),
      ("AuditLog okuma",
       lambda c, r: c.get(reverse("mission-audit", args=[gorev.id])),
       {"owner":200,"operator":200,"viewer":200,"uye_olmayan":404},
       "test_denetim.py::test_viewer_denetimi_okuyabilir", ""),
      ("AuditLog yazma girisimi",
       lambda c, r: c.post(reverse("mission-audit", args=[gorev.id]),
                           {"action":"member_added"}, format="json"),
       {"owner":405,"operator":405,"viewer":405,"uye_olmayan":405},
       "test_yetki_matrisi.py::test_denetim_yazma_hicbir_rolde_mumkun_degil",
       "Yazma ucu YOK. Uye olmayan da 405 alir: DRF yontem denetimini yetkiden "
       "ONCE yapar. Bilgi sizmasi yok, 405 gorevin varligini soylemez"),
    ]

satirlar = []
for ad, cagri, beklenen, test, notu in ISLEMLER():
    gercek = {}
    for rol_adi, kul in ROLLER:
        try:
            yanit = cagri(istemci(kul), rol_adi)
            gercek[rol_adi] = yanit.status_code
        except Exception as hata:
            gercek[rol_adi] = "HATA:" + type(hata).__name__
    gecti = all(gercek[r] == beklenen[r] for r, _ in ROLLER)
    satirlar.append({
        "islem": ad,
        "owner": gercek["owner"], "operator": gercek["operator"],
        "viewer": gercek["viewer"], "uye_olmayan": gercek["uye_olmayan"],
        "beklenen_http": " ".join(f"{r}={beklenen[r]}" for r, _ in ROLLER),
        "gercek_http": " ".join(f"{r}={gercek[r]}" for r, _ in ROLLER),
        "gecti_kaldi": "gecti" if gecti else "KALDI",
        "test": test, "not": notu,
    })

# /media/ bypass kontrolu ayri: DRF istemcisi degil duz Django istemcisi.
duz = Client()
media_yanit = duz.get("/media/" + kare.image.name)
satirlar.append({
    "islem": "/media/ ile goruntuye dogrudan erisim",
    "owner": media_yanit.status_code, "operator": media_yanit.status_code,
    "viewer": media_yanit.status_code, "uye_olmayan": media_yanit.status_code,
    "beklenen_http": "hepsi=404 (yol tamamen kapali)",
    "gercek_http": f"kimliksiz={media_yanit.status_code}",
    "gecti_kaldi": "gecti" if media_yanit.status_code == 404 else "KALDI",
    "test": "test_yetki_matrisi.py::test_media_yolu_artik_servis_edilmiyor",
    "not": "Hafta 5'te bu yol 200 doneruyordu ve uyelik denetimini dolasiyordu",
})

temizle()
print("YETKI_MATRISI=" + json.dumps(satirlar))
'''


def main():
    cikti_yolu = Path(sys.argv[1]) if len(sys.argv) > 1 else VARSAYILAN_CIKTI

    kabuk = subprocess.run(
        ["docker", "compose", "exec", "-T", "web", "python", "manage.py", "shell", "-c",
         KABUK_KODU],
        cwd=DEPO_KOKU, capture_output=True, text=True, timeout=900,
    )
    if kabuk.returncode != 0:
        print(kabuk.stdout[-4000:])
        print(kabuk.stderr[-4000:], file=sys.stderr)
        raise SystemExit("Yetki matrisi uretilemedi.")

    satir = next(
        (s for s in kabuk.stdout.splitlines() if s.startswith("YETKI_MATRISI=")), None
    )
    if satir is None:
        print(kabuk.stdout[-4000:])
        raise SystemExit("Sonuc satiri bulunamadi.")

    satirlar = json.loads(satir[len("YETKI_MATRISI="):])
    kosu = {
        "kosu_tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kosu_python": platform.python_version(),
        "kosu_komut": "python scripts/24_yetki_matrisi.py",
        "kosu_kapsam_notu": (
            "Kodlar GERCEK cagrilardan okundu, elle yazilmadi. Gecici gorev ve "
            "kullanicilar olcum sonunda silindi."
        ),
    }

    cikti_yolu.parent.mkdir(parents=True, exist_ok=True)
    with open(cikti_yolu, "w", newline="", encoding="utf-8") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=SUTUNLAR)
        yazici.writeheader()
        for veri in satirlar:
            veri.update(kosu)
            yazici.writerow({s: veri.get(s, "") for s in SUTUNLAR})

    kalan = [s for s in satirlar if s["gecti_kaldi"] != "gecti"]
    for s in satirlar:
        print(f"  [{s['gecti_kaldi']:6}] {s['islem']:38} {s['gercek_http']}")
    print(f"\n{len(satirlar)} islem, {len(kalan)} kaldi.")
    print(f"Yazildi: {cikti_yolu.relative_to(DEPO_KOKU)}")
    return 1 if kalan else 0


if __name__ == "__main__":
    sys.exit(main())
