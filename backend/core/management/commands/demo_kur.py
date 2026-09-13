"""Tek komutla uctan uca bir Gozcu tanitim akisi kurar.

NEDEN VAR: Projeyi ilk kez acan biri sistemi gorebilmek icin sirayla kullanici
olusturmak, gorev acmak, goruntu yuklemek, tarama baslatmak, inceleme girmek ve
bulgu olusturmak zorunda kalmasin. Bu komut o zinciri kurar ve hangi verinin
sentetik oldugunu her katmanda yazar.

KAYNAK SECIMI (--kaynak):
  auto     : gercek model dosyasi ve veri kumesi varsa "gercek", yoksa "sentetik"
  gercek   : yerel HERIDAL karelerini gercek ONNX modeliyle tarar (yavas, ~30 sn/kare)
  sentetik : uretilmis goruntuleri `fake-v0` test dedektoruyle tarar (hizli)

SENTETIK MODDA TESPITLER BIR MODELIN CIKTISI DEGILDIR. `fake-v0`, boru hattini
modelin yavasligindan bagimsiz dogrulamak icin Hafta 2'de yazilmis, sabit
tohumlu bir test dedektorudur. Gorev aciklamasina ve komut ciktisina bu
yaziliyor; olculmus dogruluk sayilari icin rapora bakilir.

Bu komut GERCEK GPS URETMEZ. Uretilen koordinatlar sabit tohumlu sentetik
degerlerdir (core/demo.py) ve `location_source = demo` ile saklanir.

Kosu:
    docker compose exec web python manage.py demo_kur
    docker compose exec web python manage.py demo_kur --kaynak sentetik --kare 3
    docker compose exec web python manage.py demo_kur --sil
"""
import random
import secrets
import time
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageDraw

from core.demo import TANITIM_GOREV_ADI, TOHUM, konum_bulgulari
from core.denetim import denetim_yaz
from core.kumeleme import gorevi_kumele
from core.models import (
    AuditLog,
    Detection,
    Finding,
    Frame,
    InferenceRun,
    Mission,
    MissionMember,
    ModelVersion,
    Review,
)
from core.services import ingest_frame
from core.tasks import run_inference

#: Demo hesaplari. Rolleri farkli: arayuzdeki yetki ayrimi gorulebilsin.
SAHIP_ADI = "demo"
IZLEYICI_ADI = "demo_izleyici"

#: Depoda SABIT BIR DEMO PAROLASI YOKTUR. Parola verilmezse her kosuda
#: rastgele uretilir ve ekrana yazilir; boylece bilinen bir parola hicbir
#: kuruluma girmez. Ayni parolayi tekrar kullanmak icin DEMO_PAROLA ortam
#: degiskeni verilir -- demo.sh ilk kosuda bunu uretip .env'e yazar.
PAROLA_UZUNLUGU = 12

#: Gercek kareler icin aranan dizinler (konteyner ici ve konteyner disi).
GERCEK_KARE_DIZINLERI = (
    "/data/heridal/test/images",
    "data/heridal/test/images",
)

#: Sentetik kare olculeri: gercek veri kumesiyle AYNI geometri, boylece
#: karolama davranisi demo ile olcumde ayni sekilde gorunur.
SENTETIK_GENISLIK = 4000
SENTETIK_YUKSEKLIK = 3000


def _sentetik_kare(sira: int) -> bytes:
    """Havadan cekilmis bir sahneyi ANDIRAN, tamamen uretilmis bir goruntu.

    Gercek bir fotograf degildir ve icindeki figurler gercek insan degildir;
    amaci arayuzun ve karolama hattinin uzerinde calisabilecegi, boyutu gercek
    veriyle ayni bir goruntu saglamaktir."""
    uretec = random.Random(TOHUM + sira)
    gorsel = Image.new("RGB", (SENTETIK_GENISLIK, SENTETIK_YUKSEKLIK), (104, 118, 86))
    cizici = ImageDraw.Draw(gorsel)

    # Arazi dokusu: farkli tonlarda lekeler. Gercek bir ortofoto degil, ama duz
    # zemin yerine degisken bir arka plan verir.
    for _ in range(900):
        x = uretec.randint(0, SENTETIK_GENISLIK)
        y = uretec.randint(0, SENTETIK_YUKSEKLIK)
        r = uretec.randint(20, 260)
        ton = uretec.randint(-28, 28)
        cizici.ellipse(
            [x - r, y - r, x + r, y + r],
            fill=(max(0, 104 + ton), max(0, 118 + ton), max(0, 86 + ton)),
        )

    # Insan buyuklugunde birkac koyu figur: veri kumesindeki medyan hedef
    # 60x59 piksel; benzer olcekte birakiliyor.
    for _ in range(6):
        x = uretec.randint(200, SENTETIK_GENISLIK - 200)
        y = uretec.randint(200, SENTETIK_YUKSEKLIK - 200)
        cizici.ellipse([x, y, x + 34, y + 58], fill=(48, 40, 38))

    cizici.text((40, 40), f"GOZCU DEMO - SENTETIK GORUNTU #{sira}", fill=(255, 255, 255))

    tampon = BytesIO()
    gorsel.save(tampon, format="JPEG", quality=82)
    return tampon.getvalue()


def _gercek_kare_adaylari(adet: int) -> list[Path]:
    """Yerel HERIDAL test bolumunden ilk N kareyi dondurur; yoksa bos liste."""
    for dizin in GERCEK_KARE_DIZINLERI:
        yol = Path(dizin)
        if yol.is_dir():
            adaylar = sorted(yol.glob("*.jpg"))[:adet]
            if adaylar:
                return adaylar
    return []


class Command(BaseCommand):
    help = "Uctan uca demo verisi kurar: kullanici, gorev, kare, tarama, inceleme, bulgu."

    def add_arguments(self, ayristirici):
        ayristirici.add_argument(
            "--kaynak", choices=("auto", "gercek", "sentetik"), default="auto",
            help="Kare ve dedektor kaynagi.",
        )
        ayristirici.add_argument("--kare", type=int, default=3, help="Kare sayisi.")
        ayristirici.add_argument(
            "--parola", default=None,
            help="Demo hesaplarinin parolasi. Verilmezse DEMO_PAROLA ortam "
                 "degiskeni, o da yoksa yerel demo varsayilani kullanilir.",
        )
        ayristirici.add_argument(
            "--bekleme", type=int, default=900,
            help="Taramanin bitmesi icin beklenecek en fazla sure (saniye).",
        )
        ayristirici.add_argument(
            "--tarama-yok", action="store_true",
            help="Tarama baslatma; yalnizca kullanici, gorev ve kareleri kur.",
        )
        ayristirici.add_argument(
            "--sil", action="store_true", help="Demo gorevini ve verisini siler."
        )

    # --- yardimcilar ------------------------------------------------------

    def _parolayi_coz(self, secenekler):
        """(parola, uretildi_mi) dondurur."""
        import os

        verilen = secenekler["parola"] or os.environ.get("DEMO_PAROLA")
        if verilen:
            return verilen, False
        return "demo-" + secrets.token_urlsafe(PAROLA_UZUNLUGU), True

    def _kaynagi_sec(self, istenen, kare_sayisi):
        """(kaynak, kareler) dondurur. Gercek mod icin hem model hem veri sart."""
        model_var = bool(settings.ONNX_MODEL_PATH) and Path(settings.ONNX_MODEL_PATH).is_file()
        kareler = _gercek_kare_adaylari(kare_sayisi)

        if istenen == "gercek":
            if not model_var:
                raise CommandError(
                    f"Gercek mod icin ONNX model dosyasi gerekli: "
                    f"{settings.ONNX_MODEL_PATH or '(ONNX_MODEL_PATH bos)'}"
                )
            if not kareler:
                raise CommandError(
                    "Gercek mod icin yerel veri kumesi gerekli. Aranan dizinler: "
                    + ", ".join(GERCEK_KARE_DIZINLERI)
                )
            return "gercek", kareler

        if istenen == "auto" and model_var and kareler:
            return "gercek", kareler
        return "sentetik", []

    def _kullanicilari_kur(self, parola):
        Kullanici = get_user_model()
        sahip, _ = Kullanici.objects.get_or_create(
            username=SAHIP_ADI, defaults={"is_staff": False}
        )
        sahip.set_password(parola)
        sahip.save(update_fields=["password"])

        izleyici, _ = Kullanici.objects.get_or_create(username=IZLEYICI_ADI)
        izleyici.set_password(parola)
        izleyici.save(update_fields=["password"])
        return sahip, izleyici

    def _gorevi_kur(self, sahip, izleyici, kaynak):
        if kaynak == "gercek":
            aciklama = (
                "Tanıtım görevi. Kareler yerel HERIDAL test bölümünden alındı ve "
                "gerçek Model-512 ONNX ağırlığıyla tarandı. Konum bilgisi "
                "SENTETİKTİR: veri kümesinde EXIF GPS yoktur."
            )
        else:
            aciklama = (
                "Tanıtım görevi. Kareler üretilmiş sentetik görüntülerdir ve "
                "tespitler eğitilmiş bir modelin çıktısı DEĞİLDİR; boru hattını "
                "doğrulamak için yazılmış `fake-v0` test dedektöründen gelir. "
                "Konum bilgisi de sentetiktir."
            )

        gorev, yeni = Mission.objects.get_or_create(
            name=TANITIM_GOREV_ADI,
            defaults={"description": aciklama, "created_by": sahip},
        )
        if not yeni:
            # Idempotanslik: ikinci kosu kayitlari ikiye katlamasin.
            Frame.objects.filter(mission=gorev).delete()
            InferenceRun.objects.filter(mission=gorev).delete()
            Finding.objects.filter(mission=gorev).delete()
            Mission.objects.filter(pk=gorev.pk).update(description=aciklama)
            gorev.refresh_from_db()

        MissionMember.objects.update_or_create(
            mission=gorev, user=sahip,
            defaults={"role": MissionMember.Role.OWNER, "added_by": sahip},
        )
        MissionMember.objects.update_or_create(
            mission=gorev, user=izleyici,
            defaults={"role": MissionMember.Role.VIEWER, "added_by": sahip},
        )
        return gorev

    def _kareleri_yukle(self, gorev, kaynak, kareler, kare_sayisi):
        yuklenen = []
        if kaynak == "gercek":
            for yol in kareler:
                dosya = SimpleUploadedFile(
                    yol.name, yol.read_bytes(), content_type="image/jpeg"
                )
                kare, _ = ingest_frame(gorev, dosya)
                yuklenen.append(kare)
        else:
            for sira in range(1, kare_sayisi + 1):
                dosya = SimpleUploadedFile(
                    f"demo_sentetik_{sira:02d}.jpg",
                    _sentetik_kare(sira),
                    content_type="image/jpeg",
                )
                kare, _ = ingest_frame(gorev, dosya)
                yuklenen.append(kare)
        return yuklenen

    def _taramayi_calistir(self, gorev, sahip, kaynak, bekleme):
        surum_adi = "model512-onnx" if kaynak == "gercek" else "fake-v0"
        surum = ModelVersion.objects.filter(name=surum_adi).first()
        if surum is None:
            raise CommandError(f"ModelVersion bulunamadi: {surum_adi}")

        with transaction.atomic():
            kosu = InferenceRun.objects.create(
                mission=gorev,
                model_version=surum,
                conf_threshold=0.30,
                iou_threshold=0.30,
                tile_size=surum.tile_size,
                overlap_ratio=surum.overlap_ratio,
                status=InferenceRun.Status.PENDING,
                frames_total=Frame.objects.filter(mission=gorev).count(),
            )
            denetim_yaz(
                actor=sahip, mission=gorev, action=AuditLog.Action.RUN_STARTED,
                nesne=kosu, ek={"model": surum_adi, "kaynak": kaynak},
            )

        run_inference.delay(kosu.id)
        self.stdout.write(f"Tarama kuyruga alindi (kosu {kosu.id}, model {surum_adi}).")

        bitis = time.monotonic() + bekleme
        son_bildirilen = -1
        while time.monotonic() < bitis:
            kosu.refresh_from_db()
            if kosu.frames_done != son_bildirilen:
                self.stdout.write(
                    f"  {kosu.frames_done}/{kosu.frames_total} kare "
                    f"({kosu.status})", ending="\r"
                )
                son_bildirilen = kosu.frames_done
            if kosu.status in (InferenceRun.Status.DONE, InferenceRun.Status.FAILED):
                self.stdout.write("")
                return kosu
            time.sleep(2)

        raise CommandError(
            f"Tarama {bekleme} saniyede bitmedi (durum: {kosu.status}). "
            "Celery isci calisyor mu? `docker compose logs worker` bakin."
        )

    def _incelemeleri_gir(self, kosu, gorev, sahip):
        """En yuksek skorlu tespitleri onaylar, birkacini eler.

        Amac, operatör kararinin model ciktisindan AYRI bir kayit oldugunu
        arayuzde gosterebilmek; bu kararlar bir dogruluk olcumu degildir."""
        tespitler = list(
            Detection.objects.filter(inference_run=kosu).order_by("-score")[:8]
        )
        # Uc karar turu de gorunsun: dogrulandi / belirsiz / reddedildi.
        kararlar = (
            Review.Decision.ACCEPTED,
            Review.Decision.ACCEPTED,
            Review.Decision.UNCERTAIN,
            Review.Decision.REJECTED,
        )
        onaylanan = []
        for sira, tespit in enumerate(tespitler):
            karar = kararlar[sira % len(kararlar)]
            with transaction.atomic():
                inceleme, yeni = Review.objects.update_or_create(
                    detection=tespit, reviewer=sahip,
                    defaults={
                        "decision": karar,
                        "note": "Demo incelemesi; gerçek bir operatör kararı değildir.",
                    },
                )
                denetim_yaz(
                    actor=sahip, mission=gorev,
                    action=(AuditLog.Action.REVIEW_CREATED if yeni
                            else AuditLog.Action.REVIEW_UPDATED),
                    nesne=inceleme, sonraki={"decision": karar},
                )
            if karar == Review.Decision.ACCEPTED:
                onaylanan.append(tespit)
        return len(tespitler), len(onaylanan)

    def _bulgulari_kur(self, gorev, sahip):
        kayitlar = konum_bulgulari(gorev, sahip)
        Finding.objects.bulk_create(kayitlar)
        for bulgu in Finding.objects.filter(mission=gorev):
            denetim_yaz(
                actor=sahip, mission=gorev, action=AuditLog.Action.FINDING_CREATED,
                nesne=bulgu, sonraki={"title": bulgu.title,
                                      "location_source": bulgu.location_source},
            )
        return Finding.objects.filter(mission=gorev).count()

    # --- ana akis ---------------------------------------------------------

    def handle(self, *args, **secenekler):
        if secenekler["sil"]:
            silinen, _ = Mission.objects.filter(name=TANITIM_GOREV_ADI).delete()
            self.stdout.write(f"Demo gorevi silindi ({silinen} kayit).")
            self.stdout.write(
                "Demo kullanicilari BIRAKILDI. Silmek icin: "
                f"manage.py shell -c \"from django.contrib.auth import get_user_model; "
                f"get_user_model().objects.filter(username__in=['{SAHIP_ADI}',"
                f"'{IZLEYICI_ADI}']).delete()\""
            )
            return

        parola, uretildi = self._parolayi_coz(secenekler)
        kaynak, kareler = self._kaynagi_sec(secenekler["kaynak"], secenekler["kare"])
        kare_sayisi = len(kareler) if kaynak == "gercek" else secenekler["kare"]

        self.stdout.write(f"Kaynak: {kaynak} ({kare_sayisi} kare)")
        if kaynak == "sentetik":
            self.stdout.write(self.style.WARNING(
                "Sentetik mod: goruntuler uretilmistir ve tespitler egitilmis bir "
                "modelin ciktisi DEGILDIR (fake-v0 test dedektoru)."
            ))

        sahip, izleyici = self._kullanicilari_kur(parola)
        gorev = self._gorevi_kur(sahip, izleyici, kaynak)
        yuklenen = self._kareleri_yukle(gorev, kaynak, kareler, kare_sayisi)
        self.stdout.write(f"Gorev {gorev.id}: {len(yuklenen)} kare yuklendi.")

        kosu = None
        if not secenekler["tarama_yok"]:
            kosu = self._taramayi_calistir(gorev, sahip, kaynak, secenekler["bekleme"])
            tespit_sayisi = Detection.objects.filter(inference_run=kosu).count()
            self.stdout.write(
                f"Tarama bitti: durum {kosu.status}, {tespit_sayisi} tespit."
            )
            incelenen, onaylanan = self._incelemeleri_gir(kosu, gorev, sahip)
            self.stdout.write(
                f"{incelenen} tespit incelendi, {onaylanan} tanesi dogrulandi."
            )

        bulgu_sayisi = self._bulgulari_kur(gorev, sahip)
        with transaction.atomic():
            ozet = gorevi_kumele(gorev, aktor=sahip)
            denetim_yaz(
                actor=sahip, mission=gorev, action=AuditLog.Action.CLUSTER_RUN,
                object_type="Mission", object_id=str(gorev.id), ek=ozet,
            )
        self.stdout.write(
            f"{bulgu_sayisi} bulgu, {ozet['kume_sayisi']} kume olustu "
            f"({ozet['konumsuz_bulgu']} konumsuz)."
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo hazir."))
        self.stdout.write(f"  Gorev      : {gorev.name} (id {gorev.id})")
        if kosu is not None:
            self.stdout.write(f"  Kosu       : {kosu.id}")
        self.stdout.write(f"  Operator   : {SAHIP_ADI} / {parola}")
        self.stdout.write(f"  Izleyici   : {IZLEYICI_ADI} / {parola}  (salt okunur)")
        if uretildi:
            self.stdout.write(
                "  (Parola bu kosuda uretildi. Ayni parolayi korumak icin "
                "DEMO_PAROLA ortam degiskenini verin.)"
            )
        self.stdout.write("")
        self.stdout.write(
            "UYARI: Koordinatlar sentetiktir, gercek GPS degildir. Tespitler "
            "operator kararinin yerine gecmez."
        )
