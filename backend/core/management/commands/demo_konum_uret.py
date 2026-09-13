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

Koordinat uretimi core/demo.py icindedir; uctan uca tanitim akisini kuran
`demo_kur` komutu ayni fonksiyonu kullanir.

Kosu:
    docker compose exec web python manage.py demo_konum_uret --kullanici <ad>
    docker compose exec web python manage.py demo_konum_uret --sil
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.demo import (
    KONUM_GOREV_ADI,
    VARSAYILAN_BOYLAM,
    VARSAYILAN_ENLEM,
    konum_bulgulari,
)
from core.models import Finding, Mission, MissionMember

#: Geriye donuk ad: olcum kayitlari ve eski metinler bu adi kullaniyor.
DEMO_GOREV_ADI = KONUM_GOREV_ADI


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

        olusturulan = konum_bulgulari(
            gorev, kullanici, secenekler["enlem"], secenekler["boylam"]
        )
        Finding.objects.bulk_create(olusturulan)

        self.stdout.write(self.style.SUCCESS(
            f"Demo gorevi hazir (id={gorev.id}): {len(olusturulan)} bulgu, "
            f"{len(olusturulan) - 1} tanesi demo konumlu, 1 tanesi konumsuz."
        ))
        self.stdout.write(
            "UYARI: Bu koordinatlar sentetiktir. Gercek GPS verisi degildir ve "
            "gercek bir olay yerini gostermez."
        )
