"""Olcum kosusu: bir klasordeki goruntuleri yeni bir goreve alir ve GERCEK
Celery kuyruguna gonderip bitmesini bekler.

Gorev fonksiyonu DOGRUDAN CAGRILMAZ: kayit, ucun kullandigi yolun aynisiyla
olusturulur ve run_inference.delay() ile kuyruga birakilir; isi calisan isci
yapar. Boylece olculen sey gercek kuyruk davranisidir.

Cikti stdout'a tek bir JSON nesnesidir; cagiran script (scripts/19, scripts/20)
bunu okur.
"""
import json
import time
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from core.models import Detection, Frame, InferenceRun, Mission, ModelVersion
from core.services import ingest_frame
from core.tasks import run_inference

GECERLI_UZANTILAR = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SON_DURUMLAR = {Frame.Status.DONE, Frame.Status.FAILED}


class Command(BaseCommand):
    help = "Bir klasoru yeni bir goreve alir, gercek kuyrukta tarar ve JSON ozet basar."

    def add_arguments(self, ayrastirici):
        ayrastirici.add_argument("--goruntu-dizini", required=True)
        ayrastirici.add_argument("--gorev-adi", required=True)
        ayrastirici.add_argument("--model-surumu", default="model512-onnx")
        ayrastirici.add_argument("--kullanici", default="")
        ayrastirici.add_argument("--conf", type=float, default=0.30)
        ayrastirici.add_argument("--iou", type=float, default=0.3)
        ayrastirici.add_argument("--limit", type=int, default=0)
        ayrastirici.add_argument(
            "--bekleme-siniri", type=float, default=3600.0,
            help="Butun kareler son duruma ulasana kadar beklenecek ust sinir (sn)",
        )
        ayrastirici.add_argument(
            "--yoklama-araligi", type=float, default=2.0,
            help="Veritabani durum sorgularinin araligi (sn)",
        )
        ayrastirici.add_argument(
            "--baslatma", default="hemen", choices=["hemen", "bekle"],
            help="'bekle': kayitlar hazirlanir, kuyruga birakilmaz (cagiran baslatir)",
        )

    def handle(self, *args, **secenekler):
        dizin = Path(secenekler["goruntu_dizini"])
        if not dizin.is_dir():
            raise CommandError(f"Goruntu dizini yok: {dizin}")

        model_surumu = ModelVersion.objects.filter(name=secenekler["model_surumu"]).first()
        if model_surumu is None:
            raise CommandError(f"ModelVersion bulunamadi: {secenekler['model_surumu']}")

        kullanici = (
            User.objects.filter(username=secenekler["kullanici"]).first()
            if secenekler["kullanici"] else User.objects.order_by("id").first()
        )
        if kullanici is None:
            raise CommandError("Gorev sahibi olacak kullanici bulunamadi")

        gorev = Mission.objects.create(
            name=secenekler["gorev_adi"],
            created_by=kullanici,
            description="Hafta 4 olcum kosusu; scripts/19 ve scripts/20 tarafindan uretildi.",
        )

        dosyalar = sorted(
            y for y in dizin.iterdir()
            if y.is_file() and y.suffix.lower() in GECERLI_UZANTILAR
        )
        if secenekler["limit"]:
            dosyalar = dosyalar[: secenekler["limit"]]
        if not dosyalar:
            raise CommandError(f"Dizinde goruntu yok: {dizin}")

        alinan = []
        for yol in dosyalar:
            with yol.open("rb") as dosya:
                kare, kopya = ingest_frame(gorev, File(dosya, name=yol.name))
            alinan.append({"frame_id": kare.id, "dosya": yol.name, "kopya": kopya})

        kare_sayisi = Frame.objects.filter(mission=gorev).count()
        kosu = InferenceRun.objects.create(
            mission=gorev,
            model_version=model_surumu,
            conf_threshold=secenekler["conf"],
            iou_threshold=secenekler["iou"],
            tile_size=model_surumu.tile_size,
            overlap_ratio=model_surumu.overlap_ratio,
            status=InferenceRun.Status.PENDING,
            frames_total=kare_sayisi,
        )

        ozet = {
            "gorev_id": gorev.id,
            "gorev_adi": gorev.name,
            "kosu_id": kosu.id,
            "model_surumu": model_surumu.name,
            "model_cercevesi": model_surumu.framework,
            "kullanici": kullanici.username,
            "kare_sayisi": kare_sayisi,
            "alinan": alinan,
            "kosu_baslangici": kosu.started_at.isoformat(),
        }

        if secenekler["baslatma"] == "bekle":
            ozet["durum"] = "kuyruga_birakilmadi"
            self.stdout.write(json.dumps(ozet, ensure_ascii=False))
            return

        baslangic = time.perf_counter()
        # Ucun yaptigi gibi: kayit COMMIT olduktan SONRA kuyruga birak.
        with transaction.atomic():
            transaction.on_commit(lambda: run_inference.delay(kosu.id))
        ozet["kuyruga_birakildi"] = timezone.now().isoformat()

        son = self._bitmesini_bekle(
            gorev, secenekler["bekleme_siniri"], secenekler["yoklama_araligi"]
        )
        ozet.update(son)
        ozet["toplam_sure"] = time.perf_counter() - baslangic
        ozet["tespit_sayisi"] = Detection.objects.filter(inference_run=kosu).count()
        kosu.refresh_from_db()
        ozet["kosu_durumu"] = kosu.status
        ozet["kosu_frames_done"] = kosu.frames_done
        ozet["kosu_frames_failed"] = kosu.frames_failed
        self.stdout.write(json.dumps(ozet, ensure_ascii=False))

    def _bitmesini_bekle(self, gorev, sinir, aralik):
        """Butun kareler son duruma ulasana kadar kontrollu araliklarla sorgular."""
        baslangic = time.perf_counter()
        while True:
            durumlar = dict(
                Frame.objects.filter(mission=gorev)
                .values_list("status")
                .annotate(sayi=Count("id"))
            )
            kalan = sum(
                sayi for durum, sayi in durumlar.items() if durum not in SON_DURUMLAR
            )
            if kalan == 0:
                return {"durumlar": durumlar, "bekleme_asildi": False,
                        "bekleme_suresi": time.perf_counter() - baslangic}
            if time.perf_counter() - baslangic > sinir:
                return {"durumlar": durumlar, "bekleme_asildi": True,
                        "bekleme_suresi": time.perf_counter() - baslangic}
            time.sleep(aralik)
