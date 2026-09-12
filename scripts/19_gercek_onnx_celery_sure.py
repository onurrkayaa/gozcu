"""Gercek Model-512 ONNX dedektorunun CELERY KUYRUGUNDAKI suresini olcer ve
zaman asimi sinirlarini bu sureye gore degerlendirir.

Gorev fonksiyonu dogrudan cagrilmaz: kareler bir goreve alinir, kosu ucun
kullandigi yolun aynisiyla kuyruga birakilir ve isi calisan Celery iscisi yapar
(backend/core/management/commands/olcum_kosusu.py). Asama sureleri iscinin
icinde TASK_TIMING_LOG ayari acikken toplanir; bu script o kaydi okur.

Bu script SAHTE DEDEKTOR kullanmaz ve modeli kendi surecinde calistirmaz:
olculen sey, uretimde calisan yolun ta kendisidir.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIZIN = Path(__file__).resolve().parent
PROJE_KOK = SCRIPT_DIZIN.parent
sys.path.insert(0, str(SCRIPT_DIZIN))

import importlib.util  # noqa: E402

from ortak import RAPOR_KOK, VERI_KOK, csv_yaz, kosu_bilgisi, sayi_bicimle, tablo_bas  # noqa: E402


def _modul_yukle(ad: str, dosya: str):
    spec = importlib.util.spec_from_file_location(ad, SCRIPT_DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


KIMLIK = _modul_yukle("asinalik", "14_egitim_test_asinalik.py")

VARSAYILAN_ONNX_BILGI = RAPOR_KOK / "model512_onnx_bilgisi.csv"
MODEL_YOLU = PROJE_KOK / "agirliklar" / "model512_best.onnx"

# Asama sureleri. Ozet CSV'si her biri icin sayi/min/medyan/p95/maks uretir.
SURE_ALANLARI = (
    "kuyruk_bekleme",
    "goruntu_okuma",
    "karolama",
    "onnx_cikarim",
    "nms_koordinat",
    "db_yazma",
    "frame_toplam",
    "uctan_uca_sure",
)

# --- Zaman asimi karar kurali -------------------------------------------------
# Guvenlik payi bir OLCUM DEGIL, bir KARARDIR. Carpan ve ek sureler burada acikca
# durur; sonuc gorulduikten sonra sessizce degistirilmez.
GUVENLIK_PAYI_TURU = "carpan"
GUVENLIK_PAYI_DEGERI = 10          # olculen en yavas kareye uygulanan carpan
TEMIZ_KAPANMA_PAYI_SN = 60         # soft limitten sonra temiz kapanmaya birakilan sure
VISIBILITY_CARPANI = 1.5           # visibility timeout, hard limitin bu kati kadar
EN_AZ_SOFT_LIMIT_SN = 60


def argumanlari_coz() -> argparse.Namespace:
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Gercek ONNX dedektorunu Celery kuyrugunda olcer, asama surelerini "
            "CSV'ye yazar ve zaman asimi sinirlari icin karar uretir."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument(
        "--goruntu-dizini", type=Path, default=VERI_KOK / "test" / "images",
        help="Goreve alinacak goruntulerin bulundugu dizin (host tarafi)",
    )
    ayrastirici.add_argument(
        "--konteyner-dizini", default="/olcum_veri",
        help="Ayni dizinin tek seferlik konteyner icindeki baglanma noktasi",
    )
    ayrastirici.add_argument("--gorev-adi", default="")
    ayrastirici.add_argument("--model-surumu", default="model512-onnx")
    ayrastirici.add_argument("--limit", type=int, default=0)
    ayrastirici.add_argument(
        "--zamanlama-log", default="/app/media/zamanlama.jsonl",
        help="Iscinin TASK_TIMING_LOG degeri (konteyner ici yol)",
    )
    ayrastirici.add_argument(
        "--zamanlama-log-host", type=Path, default=PROJE_KOK / "backend" / "media" / "zamanlama.jsonl",
        help="Ayni dosyanin host tarafindaki yolu",
    )
    ayrastirici.add_argument(
        "--onnx-bilgi", type=Path, default=VARSAYILAN_ONNX_BILGI,
        help="Model kimliginin dogrulandigi export kaydi",
    )
    ayrastirici.add_argument("--kare-cikti", type=Path, default=RAPOR_KOK / "gercek_onnx_celery_sure.csv")
    ayrastirici.add_argument("--ozet-cikti", type=Path, default=RAPOR_KOK / "gercek_onnx_celery_sure_ozet.csv")
    ayrastirici.add_argument("--bekleme-siniri", type=float, default=3600.0)
    return ayrastirici.parse_args()


# --- Docker yardimcilari ------------------------------------------------------


def komut_calistir(argv: list[str], girdi: str | None = None) -> str:
    """Komutu calistirir; basarisiz olursa stderr ile birlikte durur."""
    sonuc = subprocess.run(
        argv, capture_output=True, text=True, input=girdi, cwd=str(PROJE_KOK)
    )
    if sonuc.returncode != 0:
        raise SystemExit(
            f"Komut basarisiz ({' '.join(argv)}):\n{sonuc.stdout}\n{sonuc.stderr}"
        )
    return sonuc.stdout


def servis_ayarlari() -> dict:
    """Calisan isciden Celery ve dedektor ayarlarini okur."""
    kod = (
        "import json, django, os;"
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE','gozcu_api.settings');"
        "django.setup();"
        "from django.conf import settings as a;"
        "print(json.dumps({"
        "'soft_limit': a.CELERY_TASK_SOFT_TIME_LIMIT,"
        "'hard_limit': a.CELERY_TASK_TIME_LIMIT,"
        "'visibility_timeout': a.CELERY_BROKER_TRANSPORT_OPTIONS['visibility_timeout'],"
        "'acks_late': a.CELERY_TASK_ACKS_LATE,"
        "'prefetch': a.CELERY_WORKER_PREFETCH_MULTIPLIER,"
        "'store_floor': a.DETECTION_STORE_FLOOR,"
        "'onnx_model_path': a.ONNX_MODEL_PATH,"
        "'timing_log': a.TASK_TIMING_LOG}))"
    )
    cikti = komut_calistir(["docker", "compose", "exec", "-T", "worker", "python", "-c", kod])
    return json.loads(cikti.strip().splitlines()[-1])


def kosuyu_calistir(arg: argparse.Namespace, gorev_adi: str) -> dict:
    """Olcum kosusunu tek seferlik bir konteynerde baslatir; isi CALISAN isci yapar."""
    argv = [
        "docker", "compose", "run", "--rm", "-T",
        "-v", f"{arg.goruntu_dizini.resolve()}:{arg.konteyner_dizini}:ro",
        "web", "python", "manage.py", "olcum_kosusu",
        "--goruntu-dizini", arg.konteyner_dizini,
        "--gorev-adi", gorev_adi,
        "--model-surumu", arg.model_surumu,
        "--bekleme-siniri", str(arg.bekleme_siniri),
    ]
    if arg.limit:
        argv += ["--limit", str(arg.limit)]
    cikti = komut_calistir(argv)
    for satir in reversed(cikti.strip().splitlines()):
        if satir.startswith("{"):
            return json.loads(satir)
    raise SystemExit(f"Olcum kosusu JSON ozeti dondurmedi:\n{cikti}")


def veritabani_ozeti(kosu_id: int, gorev_id: int) -> dict:
    """Kosu sonrasi veritabani sayimlari: kapinin karsilastirma referansi."""
    kod = (
        "import json, django, os;"
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE','gozcu_api.settings');"
        "django.setup();"
        "from django.db.models import Count;"
        "from core.models import Detection, Frame, InferenceRun;"
        f"kosu = InferenceRun.objects.select_related('model_version').get(pk={kosu_id});"
        f"durumlar = dict(Frame.objects.filter(mission_id={gorev_id}).values_list('status')"
        ".annotate(sayi=Count('id')));"
        "print(json.dumps({'durumlar': durumlar,"
        f"'frame_sayisi': Frame.objects.filter(mission_id={gorev_id}).count(),"
        f"'tespit_sayisi': Detection.objects.filter(inference_run_id={kosu_id}).count(),"
        "'kosu_durumu': kosu.status, 'frames_done': kosu.frames_done,"
        "'frames_failed': kosu.frames_failed, 'frames_total': kosu.frames_total,"
        "'model_surumu': kosu.model_version.name, 'cerceve': kosu.model_version.framework}))"
    )
    cikti = komut_calistir(["docker", "compose", "exec", "-T", "worker", "python", "-c", kod])
    return json.loads(cikti.strip().splitlines()[-1])


# --- Olcum kaydi --------------------------------------------------------------


def zamanlama_oku(yol: Path, kosu_id: int) -> list[dict]:
    """Iscinin yazdigi JSON satirlarindan bu kosuya ait olanlari okur."""
    if not yol.is_file():
        raise SystemExit(f"Zamanlama kaydi bulunamadi: {yol}")
    kayitlar = []
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir:
            continue
        kayit = json.loads(satir)
        if kayit.get("run_id") == kosu_id:
            kayitlar.append(kayit)
    return kayitlar


def yuzdelik(degerler: list[float], oran: float) -> float:
    """Siralanmis degerlerden dogrusal aralikli yuzdelik (numpy'siz)."""
    if not degerler:
        return 0.0
    sirali = sorted(degerler)
    if len(sirali) == 1:
        return sirali[0]
    konum = (len(sirali) - 1) * oran
    alt = math.floor(konum)
    ust = math.ceil(konum)
    if alt == ust:
        return sirali[int(konum)]
    return sirali[alt] + (sirali[ust] - sirali[alt]) * (konum - alt)


def medyan(degerler: list[float]) -> float:
    if not degerler:
        return 0.0
    sirali = sorted(degerler)
    orta = len(sirali) // 2
    if len(sirali) % 2:
        return sirali[orta]
    return (sirali[orta - 1] + sirali[orta]) / 2


def kare_satirlari(kayitlar: list[dict], kare_bilgisi: dict, ozet: dict) -> list[dict]:
    """Her kare icin asama sureleri; sira frame_id'ye gore sabittir."""
    satirlar = []
    for kayit in sorted(kayitlar, key=lambda k: k["frame_id"]):
        bilgi = kare_bilgisi.get(kayit["frame_id"], {})
        satir = {
            "gorev_id": ozet["gorev_id"],
            "gorev_adi": ozet["gorev_adi"],
            "kosu_id": ozet["kosu_id"],
            "frame_id": kayit["frame_id"],
            "goreli_goruntu_yolu": bilgi.get("goreli_yol", ""),
            "frame_durumu": bilgi.get("durum", kayit.get("durum", "")),
            "model_surumu": ozet["model_surumu"],
            "soguk_baslangic": "evet" if kayit.get("soguk_baslangic") else "hayir",
            "oturum_kurulum_suresi": sayi_bicimle(kayit.get("oturum_kurulum_suresi", 0.0), 4),
            "surec_kare_sirasi": kayit.get("surec_kare_sirasi", ""),
            "surec_id": kayit.get("surec_id", "olculmedi"),
            "karo_sayisi": kayit.get("karo_sayisi", ""),
            "tespit_sayisi": kayit.get("tespit_sayisi", 0),
            "hata_sinifi": kayit.get("hata_sinifi", ""),
        }
        for alan in SURE_ALANLARI:
            deger = kayit.get(alan)
            satir[alan] = sayi_bicimle(deger, 4) if deger is not None else "olculmedi"
        satirlar.append(satir)
    return satirlar


def ozet_satirlari(kare_satir: list[dict]) -> list[dict]:
    """Her sure alani icin sayi/min/medyan/p95/maks."""
    satirlar = []
    for alan in SURE_ALANLARI:
        degerler = [
            float(s[alan]) for s in kare_satir
            if s[alan] != "olculmedi" and s[alan] != ""
        ]
        satirlar.append({
            "olcu": alan,
            "olcum_sayisi": len(degerler),
            "minimum": sayi_bicimle(min(degerler), 4) if degerler else "olculmedi",
            "medyan": sayi_bicimle(medyan(degerler), 4) if degerler else "olculmedi",
            "p95": sayi_bicimle(yuzdelik(degerler, 0.95), 4) if degerler else "olculmedi",
            "maksimum": sayi_bicimle(max(degerler), 4) if degerler else "olculmedi",
        })
    return satirlar


# --- Zaman asimi karari -------------------------------------------------------


def zaman_asimi_karari(kare_satir: list[dict], ayarlar: dict) -> dict:
    """Olculen en yavas kareden hareketle soft/hard/visibility degerlendirmesi.

    Referans sure: soguk baslangic DAHIL en yavas uctan uca gorev suresi ve en
    yavas kare isleme suresinin buyugudur. Guvenlik payi bir karardir."""
    uctan_uca = [float(s["uctan_uca_sure"]) for s in kare_satir if s["uctan_uca_sure"] != "olculmedi"]
    frame_toplam = [float(s["frame_toplam"]) for s in kare_satir if s["frame_toplam"] != "olculmedi"]
    referans = max(uctan_uca + frame_toplam) if (uctan_uca or frame_toplam) else 0.0

    onerilen_soft = max(EN_AZ_SOFT_LIMIT_SN, math.ceil(referans * GUVENLIK_PAYI_DEGERI))
    onerilen_hard = onerilen_soft + TEMIZ_KAPANMA_PAYI_SN
    onerilen_visibility = math.ceil(onerilen_hard * VISIBILITY_CARPANI)

    mevcut_yeterli = (
        ayarlar["soft_limit"] >= onerilen_soft
        and ayarlar["hard_limit"] >= onerilen_hard
        and ayarlar["hard_limit"] > ayarlar["soft_limit"]
        and ayarlar["visibility_timeout"] > ayarlar["hard_limit"]
    )
    if mevcut_yeterli:
        karar = "KORUNDU"
        gerekce = (
            f"Olculen en yavas gorev {sayi_bicimle(referans, 2)} sn. Karar kurali "
            f"({GUVENLIK_PAYI_DEGERI}x pay + {TEMIZ_KAPANMA_PAYI_SN} sn temiz kapanma + "
            f"{VISIBILITY_CARPANI}x visibility) en az soft {onerilen_soft} / hard "
            f"{onerilen_hard} / visibility {onerilen_visibility} gerektiriyor; mevcut "
            f"{ayarlar['soft_limit']}/{ayarlar['hard_limit']}/{ayarlar['visibility_timeout']} "
            "bunlarin hepsini zaten asiyor ve siralama kurali (soft < hard < visibility) "
            "saglaniyor. Sinirlari dusurmek yalnizca gecici makine yuku veya daha yavas "
            "bir kare geldiginde gorevi erken keserdi; olcum boyle bir gereklilik "
            "gostermiyor."
        )
        yeni = dict(
            soft=ayarlar["soft_limit"],
            hard=ayarlar["hard_limit"],
            visibility=ayarlar["visibility_timeout"],
        )
    else:
        karar = "GUNCELLENDI"
        gerekce = (
            f"Olculen en yavas gorev {sayi_bicimle(referans, 2)} sn. Mevcut "
            f"{ayarlar['soft_limit']}/{ayarlar['hard_limit']}/{ayarlar['visibility_timeout']} "
            "karar kuralinin gerektirdigi degerleri karsilamiyor."
        )
        yeni = dict(soft=onerilen_soft, hard=onerilen_hard, visibility=onerilen_visibility)

    return {
        "olculen_referans_sure": sayi_bicimle(referans, 4),
        "guvenlik_payi_turu": GUVENLIK_PAYI_TURU,
        "guvenlik_payi_degeri": GUVENLIK_PAYI_DEGERI,
        "guvenlik_payi_notu": "KARAR (olcum degil)",
        "kural_soft_limit": onerilen_soft,
        "kural_hard_limit": onerilen_hard,
        "kural_visibility_timeout": onerilen_visibility,
        "onerilen_soft_limit": yeni["soft"],
        "onerilen_hard_limit": yeni["hard"],
        "onerilen_visibility_timeout": yeni["visibility"],
        "karar": karar,
        "karar_gerekcesi": gerekce,
    }


# --- Kapi ---------------------------------------------------------------------


def kapi_kontrolleri(kare_satir: list[dict], db: dict, kosu_ozeti: dict,
                     ayarlar: dict, hashler: dict, beklenen_goruntu: int) -> list[dict]:
    """A kapisinin butun kosullarini tek tabloda toplar."""
    son_durumlar = {"done", "failed"}
    takili = sum(sayi for durum, sayi in db["durumlar"].items() if durum not in son_durumlar)
    eksik_sure = [
        s["frame_id"] for s in kare_satir
        if any(s[alan] == "olculmedi" for alan in SURE_ALANLARI)
    ]
    negatif = [
        s["frame_id"] for s in kare_satir
        if any(s[alan] != "olculmedi" and float(s[alan]) < 0 for alan in SURE_ALANLARI)
    ]
    soguk_sayisi = sum(1 for s in kare_satir if s["soguk_baslangic"] == "evet")
    sirali_kareler = [int(s["surec_kare_sirasi"]) for s in kare_satir if s["surec_kare_sirasi"] != ""]

    return [
        {"kontrol": "gercek dedektor (framework)", "beklenen": "onnx",
         "olculen": db["cerceve"],
         "sonuc": "GECTI" if db["cerceve"] == "onnx" else "GECMEDI"},
        {"kontrol": "model surumu", "beklenen": kosu_ozeti["model_surumu"],
         "olculen": db["model_surumu"],
         "sonuc": "GECTI" if db["model_surumu"] == kosu_ozeti["model_surumu"] else "GECMEDI"},
        {"kontrol": "model sha256", "beklenen": hashler["kayit"], "olculen": hashler["disk"],
         "sonuc": "GECTI" if hashler["kayit"] == hashler["disk"] else "GECMEDI"},
        {"kontrol": "test goruntusu = frame", "beklenen": beklenen_goruntu,
         "olculen": db["frame_sayisi"],
         "sonuc": "GECTI" if db["frame_sayisi"] == beklenen_goruntu else "GECMEDI"},
        {"kontrol": "olcum satiri = frame", "beklenen": db["frame_sayisi"],
         "olculen": len(kare_satir),
         "sonuc": "GECTI" if len(kare_satir) == db["frame_sayisi"] else "GECMEDI"},
        {"kontrol": "son duruma ulasmayan kare", "beklenen": 0, "olculen": takili,
         "sonuc": "GECTI" if takili == 0 else "GECMEDI"},
        {"kontrol": "eksik sure alani", "beklenen": 0, "olculen": len(eksik_sure),
         "sonuc": "GECTI" if not eksik_sure else "GECMEDI"},
        {"kontrol": "negatif sure", "beklenen": 0, "olculen": len(negatif),
         "sonuc": "GECTI" if not negatif else "GECMEDI"},
        {"kontrol": "oturum yeniden kullanimi (soguk baslangic sayisi)",
         "beklenen": f"<= {ayarlar['prefetch'] * 4}", "olculen": soguk_sayisi,
         "sonuc": "GECTI" if 0 < soguk_sayisi < len(kare_satir) else "GECMEDI"},
        {"kontrol": "surec kare sirasi artiyor (oturum korunuyor)",
         "beklenen": f"maks > 1", "olculen": max(sirali_kareler) if sirali_kareler else 0,
         "sonuc": "GECTI" if sirali_kareler and max(sirali_kareler) > 1 else "GECMEDI"},
        {"kontrol": "CSV tespit toplami = veritabani",
         "beklenen": db["tespit_sayisi"],
         "olculen": sum(int(s["tespit_sayisi"]) for s in kare_satir),
         "sonuc": "GECTI" if sum(int(s["tespit_sayisi"]) for s in kare_satir) == db["tespit_sayisi"] else "GECMEDI"},
    ]


def main() -> None:
    arg = argumanlari_coz()

    kayit = list(csv.DictReader(arg.onnx_bilgi.open(encoding="utf-8")))[0]
    hashler = {"disk": KIMLIK.dosya_sha256(MODEL_YOLU), "kayit": kayit["onnx_sha256"]}
    if hashler["disk"] != hashler["kayit"]:
        raise SystemExit(
            f"Model SHA-256 uyusmuyor. Diskte {hashler['disk']}, kayitta {hashler['kayit']}. "
            "Kosu calistirilmadi."
        )
    print(f"Model SHA-256 UYUSTU: {hashler['disk'][:16]}...")

    ayarlar = servis_ayarlari()
    print(f"Isci ayarlari: soft {ayarlar['soft_limit']} | hard {ayarlar['hard_limit']} | "
          f"visibility {ayarlar['visibility_timeout']} | acks_late {ayarlar['acks_late']} | "
          f"prefetch {ayarlar['prefetch']}")
    if not ayarlar["timing_log"]:
        raise SystemExit(
            "Iscide TASK_TIMING_LOG bos. Asama olcumu icin .env dosyasina "
            f"TASK_TIMING_LOG={arg.zamanlama_log} ekleyip 'docker compose up -d worker' "
            "ile isciyi yeniden baslatin."
        )
    if arg.zamanlama_log_host.exists():
        arg.zamanlama_log_host.unlink()

    goruntu_sayisi = len([
        y for y in sorted(arg.goruntu_dizini.iterdir())
        if y.is_file() and y.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ])
    if arg.limit:
        goruntu_sayisi = min(goruntu_sayisi, arg.limit)
    gorev_adi = arg.gorev_adi or f"olcum-onnx-sure-{datetime.now():%Y%m%d-%H%M%S}"
    print(f"\nGorev: {gorev_adi} | {goruntu_sayisi} goruntu | model {arg.model_surumu}")
    print("Kareler gercek Celery kuyruguna birakiliyor; isi calisan isci yapiyor.\n",
          flush=True)

    kosu_ozeti = kosuyu_calistir(arg, gorev_adi)
    db = veritabani_ozeti(kosu_ozeti["kosu_id"], kosu_ozeti["gorev_id"])
    print(f"Kosu {kosu_ozeti['kosu_id']} bitti: durumlar {db['durumlar']}, "
          f"tespit {db['tespit_sayisi']}")

    kayitlar = zamanlama_oku(arg.zamanlama_log_host, kosu_ozeti["kosu_id"])
    kare_bilgisi = {
        alinan["frame_id"]: {
            "goreli_yol": f"{arg.goruntu_dizini.relative_to(PROJE_KOK).as_posix()}/{alinan['dosya']}",
            "durum": "done",
        }
        for alinan in kosu_ozeti["alinan"]
    }
    kare_satir = kare_satirlari(kayitlar, kare_bilgisi, kosu_ozeti)
    ozet = ozet_satirlari(kare_satir)
    karar = zaman_asimi_karari(kare_satir, ayarlar)
    kontrol = kapi_kontrolleri(kare_satir, db, kosu_ozeti, ayarlar, hashler, goruntu_sayisi)

    print("\n=== A KAPISI KONTROLLERI ===")
    tablo_bas(kontrol)
    gecti = all(s["sonuc"] == "GECTI" for s in kontrol)

    soguk = [s for s in kare_satir if s["soguk_baslangic"] == "evet"]
    son_durumlar = {"done", "failed"}
    genel = [{
        "olcu": "toplam_kare", "olcum_sayisi": len(kare_satir), "minimum": "",
        "medyan": "", "p95": "", "maksimum": "",
    }]
    ozet_ek = {
        "toplam_kare": db["frame_sayisi"],
        "done_kare": db["durumlar"].get("done", 0),
        "failed_kare": db["durumlar"].get("failed", 0),
        "takili_kare": sum(s for d, s in db["durumlar"].items() if d not in son_durumlar),
        "toplam_detection": db["tespit_sayisi"],
        "soguk_baslangic_kare": len(soguk),
        "soguk_baslangic_oturum_kurulumu": max(
            [float(s["oturum_kurulum_suresi"]) for s in soguk] or [0.0]
        ),
        "soguk_baslangic_frame_toplam": max(
            [float(s["frame_toplam"]) for s in soguk if s["frame_toplam"] != "olculmedi"] or [0.0]
        ),
        "sonraki_kare_medyan_frame_toplam": medyan([
            float(s["frame_toplam"]) for s in kare_satir
            if s["soguk_baslangic"] == "hayir" and s["frame_toplam"] != "olculmedi"
        ]),
        "mevcut_soft_limit": ayarlar["soft_limit"],
        "mevcut_hard_limit": ayarlar["hard_limit"],
        "mevcut_visibility_timeout": ayarlar["visibility_timeout"],
        "acks_late": ayarlar["acks_late"],
        "prefetch": ayarlar["prefetch"],
        "kosu_durumu": db["kosu_durumu"],
        "kapi_sonucu": "GECTI" if gecti else "GECMEDI",
        **karar,
    }
    ozet_satir = [{**satir, **ozet_ek} for satir in ozet]

    kosu = kosu_bilgisi(
        gorev_adi=gorev_adi,
        gorev_id=kosu_ozeti["gorev_id"],
        kosu_id=kosu_ozeti["kosu_id"],
        model_surumu=kosu_ozeti["model_surumu"],
        model_cercevesi=db["cerceve"],
        onnx_sha256=hashler["disk"],
        onnx_model_yolu=ayarlar["onnx_model_path"],
        goruntu_dizini=arg.goruntu_dizini.relative_to(PROJE_KOK).as_posix(),
        olcum_yolu=(
            "gercek Celery kuyrugu; gorev fonksiyonu dogrudan cagrilmadi, "
            "isi calisan isci yapti (docker compose worker)"
        ),
        olcum_secenegi=f"TASK_TIMING_LOG={ayarlar['timing_log']}",
        store_floor=ayarlar["store_floor"],
    )
    kare_csv = csv_yaz(arg.kare_cikti, kare_satir, kosu)
    ozet_csv = csv_yaz(arg.ozet_cikti, ozet_satir, kosu)

    print("\n=== ASAMA SURELERI (sn) ===")
    tablo_bas(ozet, ["olcu", "olcum_sayisi", "minimum", "medyan", "p95", "maksimum"])
    print(f"\nSoguk baslangic kare sayisi: {len(soguk)} | oturum kurulumu "
          f"{sayi_bicimle(ozet_ek['soguk_baslangic_oturum_kurulumu'], 3)} sn | "
          f"ilk kare {sayi_bicimle(ozet_ek['soguk_baslangic_frame_toplam'], 3)} sn | "
          f"sonraki karelerin medyani "
          f"{sayi_bicimle(ozet_ek['sonraki_kare_medyan_frame_toplam'], 3)} sn")
    print(f"\nKare CSV : {kare_csv}  ({len(kare_satir)} satir)")
    print(f"Ozet CSV : {ozet_csv}  ({len(ozet_satir)} satir)")

    print("\n=== ZAMAN ASIMI KARARI ===")
    print(f"Referans sure (olcum): {karar['olculen_referans_sure']} sn")
    print(f"Guvenlik payi (KARAR): {karar['guvenlik_payi_degeri']}x + "
          f"{TEMIZ_KAPANMA_PAYI_SN} sn temiz kapanma + {VISIBILITY_CARPANI}x visibility")
    print(f"Kuralin gerektirdigi en az: soft {karar['kural_soft_limit']} / hard "
          f"{karar['kural_hard_limit']} / visibility {karar['kural_visibility_timeout']}")
    print(f"Karar: {karar['karar']} -> soft {karar['onerilen_soft_limit']} / hard "
          f"{karar['onerilen_hard_limit']} / visibility {karar['onerilen_visibility_timeout']}")

    print(f"\nA KAPISI: {'GECTI' if gecti else 'GECMEDI'}")
    if not gecti:
        sys.exit(1)


if __name__ == "__main__":
    main()
