"""Harita katmanini dogrulamak icin AYRI ve ACIK ADLI bir demo gorevi uretir.

NEDEN VAR: Elimizdeki veri kumesinin hicbir goruntusunde EXIF GPS yok (Hafta 5
taramasi: 1579 goruntu, 0 koordinat). Harita kodunun marker, popup ve kume
davranisini dogrulamak icinse koordinata ihtiyac var. Bu komut o koordinatlari
uretir -- ama uydurma olduklarini HER KATMANDA isaretleyerek.

NE YAPMAZ:
  - Gercek HERIDAL karelerinden koordinat TURETMEZ. Uretilen noktalar bir
    parametreden alinan taban noktanin cevresinde, sabit bir tohumla
    dagitilir; hicbir gorsel veriyle iliskisi yoktur.
  - Mevcut gorevlere DOKUNMAZ. Yalnizca kendi actigi demo gorevini yonetir.
  - Uretim ortamina kendiliginden yuklenmez; elle calistirilmasi gerekir.

Her kayit `location_source = demo` ile saklanir. API bu alani aynen dondurur,
arayuz de bu alana bakarak kalici bir "demo konumlari" uyarisi gosterir.

Kosu:
    docker compose exec web python manage.py demo_konum_uret --kullanici <ad>
    docker compose exec web python manage.py demo_konum_uret --sil
"""
import math
import random

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Finding, Mission, MissionMember

DEMO_GOREV_ADI = "DEMO — sentetik konumlar (gerçek GPS değildir)"

#: Sabit tohum: komut iki kez calistirildiginda ayni noktalar uretilir,
#: boylece ekran goruntuleri ve testler tekrarlanabilir olur.
TOHUM = 20260913

#: Taban nokta. Gercek bir olay yeri DEGILDIR; yalnizca haritanin bir yere
#: odaklanabilmesi icin secilmis bir baslangic koordinatidir.
VARSAYILAN_ENLEM = 43.5081
VARSAYILAN_BOYLAM = 16.4402


class Command(BaseCommand):
    help = "Harita dogrulamasi icin acikca etiketli demo konum verisi uretir."

    def add_arguments(self, ayristirici):
        ayristirici.add_argument(
            "--kullanici",
            help="Demo gorevinin sahibi olacak kullanici adi.",
        )
        ayristirici.add_argument("--enlem", type=float, default=VARSAYILAN_ENLEM)
        ayristirici.add_argument("--boylam", type=float, default=VARSAYILAN_BOYLAM)
        ayristirici.add_argument(
            "--sil", action="store_true", help="Demo gorevini ve bulgularini siler."
        )

    @transaction.atomic
    def handle(self, *args, **secenekler):
        if secenekler["sil"]:
            silinen, _ = Mission.objects.filter(name=DEMO_GOREV_ADI).delete()
            self.stdout.write(f"Demo gorevi silindi ({silinen} kayit).")
            return

        Kullanici = get_user_model()
        kullanici_adi = secenekler.get("kullanici")
        if not kullanici_adi:
            raise CommandError("--kullanici zorunlu: demo gorevinin sahibi gerekiyor.")
        kullanici = Kullanici.objects.filter(username=kullanici_adi).first()
        if kullanici is None:
            raise CommandError(f"Kullanici bulunamadi: {kullanici_adi}")

        gorev, yeni = Mission.objects.get_or_create(
            name=DEMO_GOREV_ADI,
            defaults={
                "description": (
                    "Bu görevdeki konumlar harita katmanını doğrulamak için "
                    "üretilmiş sentetik değerlerdir. Gerçek bir GPS ölçümü, "
                    "gerçek bir uçuş rotası veya gerçek bir olay yeri değildir."
                ),
                "created_by": kullanici,
            },
        )
        if not yeni:
            # Tekrar calistirmak kayitlari ikiye katlamasin.
            Finding.objects.filter(mission=gorev).delete()
        MissionMember.objects.get_or_create(
            mission=gorev, user=kullanici,
            defaults={"role": MissionMember.Role.OWNER, "added_by": kullanici},
        )

        taban_enlem = secenekler["enlem"]
        taban_boylam = secenekler["boylam"]
        uretec = random.Random(TOHUM)

        # Uc kume + uzakta tek nokta + konumsuz kayit: haritanin kume, tekil
        # marker ve "konum yok" durumlarini birlikte gosterebilmesi icin.
        kume_merkezleri = [(0, 0), (0, 900), (700, 400)]
        olusturulan = []

        for kume_sirasi, (dx, dy) in enumerate(kume_merkezleri, start=1):
            for uye in range(3):
                sapma_x = uretec.uniform(-20, 20)
                sapma_y = uretec.uniform(-20, 20)
                # Metre -> derece: boylamda bir derecenin metre karsiligi
                # enleme gore daralir, o yuzden kosinusle olceklenir.
                enlem = taban_enlem + (dy + sapma_y) / 111320.0
                boylam_metre_derece = 111320.0 * max(
                    0.1, abs(math.cos(math.radians(taban_enlem)))
                )
                boylam = taban_boylam + (dx + sapma_x) / boylam_metre_derece
                olusturulan.append(Finding(
                    mission=gorev,
                    title=f"Demo aday {kume_sirasi}-{uye + 1}",
                    note="Sentetik konum; gerçek bir bulgu değildir.",
                    location=Point(boylam, enlem, srid=4326),
                    location_source=Finding.LocationSource.DEMO,
                    location_note="Komutla üretilmiş demo koordinatı.",
                    status=Finding.Status.CANDIDATE,
                    created_by=kullanici,
                ))

        # Kumelerden uzakta tek nokta.
        olusturulan.append(Finding(
            mission=gorev,
            title="Demo aday — tekil",
            note="Sentetik konum; gerçek bir bulgu değildir.",
            location=Point(
                taban_boylam + 4000 / 111320.0, taban_enlem + 2500 / 111320.0, srid=4326
            ),
            location_source=Finding.LocationSource.DEMO,
            location_note="Komutla üretilmiş demo koordinatı.",
            created_by=kullanici,
        ))

        # Konumsuz kayit: arayuzun "konum yok" durumunu da gosterebilmesi icin.
        olusturulan.append(Finding(
            mission=gorev,
            title="Konumsuz aday",
            note="Bu kaydın konumu yok; harita üzerinde gösterilmez.",
            location=None,
            location_source=Finding.LocationSource.NONE,
            created_by=kullanici,
        ))

        Finding.objects.bulk_create(olusturulan)

        self.stdout.write(self.style.SUCCESS(
            f"Demo gorevi hazir (id={gorev.id}): {len(olusturulan)} bulgu, "
            f"{len(olusturulan) - 1} tanesi demo konumlu, 1 tanesi konumsuz."
        ))
        self.stdout.write(
            "UYARI: Bu koordinatlar sentetiktir. Gercek GPS verisi degildir ve "
            "gercek bir olay yerini gostermez."
        )
