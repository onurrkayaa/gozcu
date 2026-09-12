"""Celery gorevleri: asenkron tarama boru hatti.

Akis:  run_inference  ->  chord( process_frame * N )  ->  finalize_run

Onemli: settings.CELERY_TASK_ACKS_LATE acik. Isci is ortasinda olurse mesaj
kaybolmaz, yeniden dagitilir -- bedeli gorevin IKI KEZ calisabilmesidir. Bu
yuzden process_frame idempotent olmak ZORUNDA; ikisi birbirine baglidir.
"""
import json
import logging
import time

from celery import chord, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .detector import get_detector
from .models import Detection, Frame, InferenceRun
from .tiling import karodan_global_koordinata, karolari_hesapla, nms

logger = logging.getLogger(__name__)


def _zamanlama_yaz(kayit):
    """Asama surelerini JSON satiri olarak ekler; ayar bossa hicbir sey yapmaz.

    Kare basina TEK satir yazilir (karo basina degil). Olcum kapaliyken bu
    fonksiyon tek bir ayar okumasina iner, uretim davranisi degismez."""
    yol = getattr(settings, "TASK_TIMING_LOG", "")
    if not yol:
        return
    try:
        with open(yol, "a", encoding="utf-8") as dosya:
            dosya.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    except OSError:
        # Olcum kaydi uretimi bozmamali: yazilamazsa gorev normal devam eder.
        logger.warning("Zamanlama kaydi yazilamadi: %s", yol, exc_info=True)


@shared_task(name="core.run_inference")
def run_inference(run_id):
    """Kosuyu baslatir: kareleri kuyruga alir ve chord ile finalize'a baglar."""
    run = InferenceRun.objects.select_related("mission").get(pk=run_id)

    frame_ids = list(
        Frame.objects.filter(mission_id=run.mission_id)
        .order_by("id")
        .values_list("id", flat=True)
    )

    with transaction.atomic():
        InferenceRun.objects.filter(pk=run_id).update(
            status=InferenceRun.Status.RUNNING,
            frames_total=len(frame_ids),
        )
        Frame.objects.filter(id__in=frame_ids).update(status=Frame.Status.QUEUED)

    if not frame_ids:
        # Uc bu durumu 400 ile zaten engelliyor; yine de kosu asili kalmasin.
        finalize_run.delay([], run_id)
        return {"run_id": run_id, "frames": 0}

    # chord: basliktaki tum process_frame'ler bitince finalize_run calisir.
    chord(
        (process_frame.s(run_id, frame_id) for frame_id in frame_ids),
        finalize_run.s(run_id),
    ).apply_async()

    return {"run_id": run_id, "frames": len(frame_ids)}


@shared_task(
    bind=True,
    name="core.process_frame",
    max_retries=3,
    retry_backoff=True,      # ustel geri cekilme
    retry_backoff_max=120,
    retry_jitter=True,
)
def process_frame(self, run_id, frame_id):
    """Tek bir kareyi karolar, dedektoru calistirir, tespitleri yazar.

    IDEMPOTENT: ayni gorev iki kez calisirsa tespitler ikiye katlanmaz.
    """
    baslangic = time.perf_counter()
    try:
        sonuc = _process_frame_inner(run_id, frame_id)
        sonuc["uctan_uca_sure"] = time.perf_counter() - baslangic
        _zamanlama_yaz({
            "frame_id": frame_id, "run_id": run_id, "gorev_id": self.request.id,
            "durum": sonuc["status"], "hata_sinifi": "",
            "uctan_uca_sure": sonuc["uctan_uca_sure"],
            **sonuc.pop("zamanlama", {}),
        })
        return sonuc
    except SoftTimeLimitExceeded:
        # Yumusak sinir: tekrar denemenin anlami yok, kare cok agir.
        _kareyi_basarisiz_isaretle(run_id, frame_id, "zaman asimi")
        _zamanlama_yaz({
            "frame_id": frame_id, "run_id": run_id, "gorev_id": self.request.id,
            "durum": "failed", "hata_sinifi": "SoftTimeLimitExceeded",
            "uctan_uca_sure": time.perf_counter() - baslangic,
        })
        return {"frame_id": frame_id, "status": "failed", "reason": "timeout"}
    except Exception as exc:
        logger.warning(
            "Kare %s basarisiz (deneme %s): %s", frame_id, self.request.retries, exc
        )

        # Hakki kalmissa ustel geri cekilmeyle yeniden dene. self.retry() Retry
        # firlatir; bu bir HATA degil, Celery'ye "sonra tekrar dene" sinyalidir
        # ve chord'u bozmaz.
        #
        # Eager kipte yeniden denemiyoruz: orada kuyruk yok, self.retry() gorevi
        # ozyinelemeli olarak yeniden calistirip sonunda Retry'yi cagirana kadar
        # tasir. Yeniden deneme mantiginin yeri gercek isci, senkron test degil.
        if not self.request.is_eager and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        # Deneme hakki bitti. Hatayi chord'un DISINA TASIRMIYORUZ: baslikta bir
        # gorev istisna firlatirsa chord geri cagirmasi (finalize_run) calismaz
        # ve kosu sonsuza kadar "running" kalir. Bunun yerine kareyi failed
        # isaretleyip normal donuyoruz.
        _kareyi_basarisiz_isaretle(run_id, frame_id, str(exc))
        _zamanlama_yaz({
            "frame_id": frame_id, "run_id": run_id, "gorev_id": self.request.id,
            "durum": "failed", "hata_sinifi": type(exc).__name__,
            "uctan_uca_sure": time.perf_counter() - baslangic,
        })
        return {"frame_id": frame_id, "status": "failed", "reason": str(exc)}


def _process_frame_inner(run_id, frame_id):
    kare_basi = time.perf_counter()
    run = InferenceRun.objects.select_related("model_version").get(pk=run_id)
    # Kuyrukta bekleme: kosu kaydinin olustugu andan bu gorevin isciye
    # dusmesine kadar gecen sure. Tum kareler ayni chord ile kuyruga girdigi
    # icin bu, karenin sirasini bekledigi suredir.
    kuyruk_bekleme = max(0.0, (timezone.now() - run.started_at).total_seconds())

    with transaction.atomic():
        # Satir kilidi: iki isci ayni kareyi almaya calisirsa ikincisi burada
        # COMMIT'e kadar bekler, sonra satiri YENIDEN okur.
        frame = Frame.objects.select_for_update().get(pk=frame_id)

        if frame.status == Frame.Status.DONE:
            # Ilk isci isi zaten bitirmis. Dedektoru tekrar calistirmiyoruz,
            # sayaci tekrar artirmiyoruz.
            return {
                "frame_id": frame_id, "status": "already_done", "detections": 0,
                "zamanlama": {"kuyruk_bekleme": kuyruk_bekleme,
                              "frame_toplam": time.perf_counter() - kare_basi},
            }

        frame.status = Frame.Status.PROCESSING
        frame.save(update_fields=["status"])

    # Agir is kilidin DISINDA: dedektor saniyelerce surebilir, bu sure boyunca
    # Frame satirini kilitli tutmak diger iscileri bosuna bekletir.
    karolama_basi = time.perf_counter()
    karolar = karolari_hesapla(
        frame.width, frame.height, run.tile_size, run.overlap_ratio
    )
    detector = get_detector(run.model_version, frame_sha256=frame.sha256)
    # Asama sayaclari yalnizca gercek dedektorde var; sahte dedektorde bos kalir.
    if hasattr(detector, "olcum_sifirla"):
        detector.olcum_sifirla()
    karolama_suresi = time.perf_counter() - karolama_basi
    dedektor_basi = time.perf_counter()

    ham_kutular = []
    for karo in karolar:
        satir, sutun, kx1, ky1, _, _ = karo
        for kutu in detector.detect(frame.image.path, karo):
            x1, y1, x2, y2 = karodan_global_koordinata(kutu[:4], kx1, ky1)
            skor = kutu[4]
            # Depolama tabani: kosunun conf_threshold'u KAYDA PISIRILMEZ. Tek
            # pahali kosudan her esigi cevaplayabilmek icin kutular sabit bir
            # tabanla saklanir; esik okuma aninda uygulanir.
            if skor < settings.DETECTION_STORE_FLOOR:
                continue
            # Kutu goruntu sinirlarinin disina tasmasin.
            x1 = max(0, min(x1, frame.width))
            y1 = max(0, min(y1, frame.height))
            x2 = max(0, min(x2, frame.width))
            y2 = max(0, min(y2, frame.height))
            if x2 <= x1 or y2 <= y1:
                continue
            ham_kutular.append((x1, y1, x2, y2, skor, satir, sutun))

    # NMS: ortusen karolarin ayni kisiyi iki kez bulmasini temizler.
    # nms() yalnizca ilk bes ogeyi kullanir, kalanlar dokunulmadan gecer --
    # bu sayede karo indeksleri kutuya bagli kalir, sonradan eslestirmek
    # gerekmez.
    dedektor_suresi = time.perf_counter() - dedektor_basi
    nms_basi = time.perf_counter()
    nihai = nms(ham_kutular, run.iou_threshold)
    nms_suresi = time.perf_counter() - nms_basi

    sayaclar = detector.olcum_al() if hasattr(detector, "olcum_al") else {}
    # Karo dongusunde gecen sure okuma + cikarim + karo ici son islemden olusur;
    # kalan kisim (koordinat tasima, taban filtresi) son isleme eklenir.
    olculen = sum(sayaclar.values())
    koordinat_suresi = max(0.0, dedektor_suresi - olculen)

    db_basi = time.perf_counter()
    with transaction.atomic():
        # Kilidi tekrar al ve durumu YENIDEN kontrol et: agir is sirasinda baska
        # bir isci (yeniden dagitilmis bir mesajla) bitirmis olabilir.
        frame = Frame.objects.select_for_update().get(pk=frame_id)
        if frame.status == Frame.Status.DONE:
            return {
                "frame_id": frame_id, "status": "already_done", "detections": 0,
                "zamanlama": {"kuyruk_bekleme": kuyruk_bekleme,
                              "frame_toplam": time.perf_counter() - kare_basi},
            }

        # SIL-SONRA-YAZ: bu (kosu, kare) ciftinin eski tespitleri neyse silinir,
        # yenileri yazilir. Boylece ikinci calisma EKLEME degil YERINE KOYMA olur.
        Detection.objects.filter(inference_run_id=run_id, frame_id=frame_id).delete()
        Detection.objects.bulk_create(
            [
                Detection(
                    inference_run_id=run_id,
                    frame_id=frame_id,
                    score=k[4],
                    x1=k[0],
                    y1=k[1],
                    x2=k[2],
                    y2=k[3],
                    tile_row=k[5],
                    tile_col=k[6],
                )
                for k in nihai
            ]
        )

        onceki_durum = frame.status
        frame.status = Frame.Status.DONE
        frame.save(update_fields=["status"])

        # Sayac yalnizca GERCEK gecise bagli artar, F() ile atomik.
        if onceki_durum != Frame.Status.DONE:
            guncelleme = {"frames_done": F("frames_done") + 1}
            if onceki_durum == Frame.Status.FAILED:
                # Onceden basarisiz sayilmisti, simdi duzeldi: cift saymayalim.
                guncelleme["frames_failed"] = F("frames_failed") - 1
            InferenceRun.objects.filter(pk=run_id).update(**guncelleme)

    db_suresi = time.perf_counter() - db_basi
    soguk = getattr(detector, "kare_sayisi", 0) == 1
    return {
        "frame_id": frame_id,
        "status": "done",
        "detections": len(nihai),
        "zamanlama": {
            "kuyruk_bekleme": kuyruk_bekleme,
            "goruntu_okuma": sayaclar.get("goruntu_okuma", 0.0),
            "karolama": karolama_suresi,
            "onnx_cikarim": sayaclar.get("cikarim", 0.0),
            "nms_koordinat": sayaclar.get("son_islem", 0.0) + nms_suresi + koordinat_suresi,
            "db_yazma": db_suresi,
            "frame_toplam": time.perf_counter() - kare_basi,
            "tespit_sayisi": len(nihai),
            "karo_sayisi": len(karolar),
            "soguk_baslangic": soguk,
            "oturum_kurulum_suresi": getattr(detector, "kurulum_suresi", 0.0) if soguk else 0.0,
            "surec_kare_sirasi": getattr(detector, "kare_sayisi", 0),
        },
    }


def _kareyi_basarisiz_isaretle(run_id, frame_id, sebep):
    """Kareyi failed yapar ve sayaci artirir. Bu da idempotent."""
    with transaction.atomic():
        frame = Frame.objects.select_for_update().get(pk=frame_id)
        if frame.status in (Frame.Status.DONE, Frame.Status.FAILED):
            # Zaten sonuclanmis; sayaci ikinci kez artirma.
            return
        frame.status = Frame.Status.FAILED
        frame.save(update_fields=["status"])
        InferenceRun.objects.filter(pk=run_id).update(
            frames_failed=F("frames_failed") + 1
        )
    logger.error("Kare %s kosu %s icinde basarisiz: %s", frame_id, run_id, sebep)


@shared_task(name="core.finalize_run")
def finalize_run(results, run_id):
    """Kosuyu kapatir.

    En az bir kare failed olsa bile kosu DONE olur: boru hatti sonuna kadar
    islemistir ve basarili karelerin tespitleri operator icin kullanilabilir
    durumdadir. Kosunun tamamini failed isaretlemek bu isi gizlerdi. Kismi
    basarisizlik frames_failed sayacinda gorunur kalir.
    """
    with transaction.atomic():
        run = InferenceRun.objects.select_for_update().get(pk=run_id)
        if run.status == InferenceRun.Status.DONE:
            # Chord geri cagirmasi tekrarlanirsa bitis zamani degismesin.
            return {"run_id": run_id, "status": run.status}
        run.status = InferenceRun.Status.DONE
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])

    return {
        "run_id": run_id,
        "status": InferenceRun.Status.DONE,
        "frames_done": run.frames_done,
        "frames_failed": run.frames_failed,
    }
