"""Gercek ONNX modeli calisirken isciyi SIGKILL ile oldurup dayanikliligi olcer.

Dogrulanan sey Hafta 2'de kurulan sozlesmenin gercek modelle de gecerli oldugu:
    acks_late=True  ->  olen iscinin mesaji kaybolmaz, visibility timeout
                        dolunca yeniden teslim edilir
    idempotan gorev ->  yeniden teslim tespitleri ikiye katlamaz

Bu script hicbir sey ONARMAZ ve veritabanini elle duzeltmez; yalnizca olcer.
Graceful stop KULLANILMAZ: 'docker kill --signal=KILL' ile gercek SIGKILL
gonderilir ve oldugu kanitlanmadan test devam etmez.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
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
SURE = _modul_yukle("celery_sure", "19_gercek_onnx_celery_sure.py")

MODEL_YOLU = PROJE_KOK / "agirliklar" / "model512_best.onnx"
SON_DURUMLAR = ("done", "failed")
TAKILI_DURUMLAR = ("pending", "queued", "processing")

# SIGKILL'in kaniti: konteyner 128+9 ile cikar ve/veya yeniden baslatilir.
SIGKILL_CIKIS_KODU = 137


def argumanlari_coz() -> argparse.Namespace:
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Gercek ONNX modeliyle tarama surerken isciyi SIGKILL ile oldurur, "
            "gorevin yeniden teslim edildigini ve kare kaybolmadigini olcer."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--goruntu-dizini", type=Path, default=VERI_KOK / "test" / "images")
    ayrastirici.add_argument("--konteyner-dizini", default="/olcum_veri")
    ayrastirici.add_argument("--gorev-adi", default="")
    ayrastirici.add_argument("--model-surumu", default="model512-onnx")
    ayrastirici.add_argument("--kare-sayisi", type=int, default=4,
                             help="Teste alinacak kare sayisi; kucuk tutulur, sinav yeniden teslimdir")
    ayrastirici.add_argument("--isci-servisi", default="worker")
    ayrastirici.add_argument("--isci-konteyneri", default="gozcu_worker")
    ayrastirici.add_argument(
        "--zamanlama-log-host", type=Path,
        default=PROJE_KOK / "backend" / "media" / "zamanlama.jsonl",
    )
    ayrastirici.add_argument("--cikti", type=Path, default=RAPOR_KOK / "onnx_sigkill_dayaniklilik.csv")
    ayrastirici.add_argument(
        "--yoklama-araligi", type=float, default=3.0,
        help="Veritabani ve konteyner durum sorgularinin araligi (sn)",
    )
    ayrastirici.add_argument(
        "--islem-bekleme", type=float, default=180.0,
        help="En az bir karenin processing durumuna gecmesi icin ust sinir (sn)",
    )
    ayrastirici.add_argument(
        "--teslim-payi", type=float, default=0.0,
        help=(
            "Yeniden teslim ust siniri = visibility timeout + hard limit + bu pay. "
            "0 verilirse pay olarak hard limit kullanilir."
        ),
    )
    return ayrastirici.parse_args()


# --- Konteyner ve veritabani ---------------------------------------------------


def komut(argv: list[str], hataya_izin: bool = False) -> str:
    sonuc = subprocess.run(argv, capture_output=True, text=True, cwd=str(PROJE_KOK))
    if sonuc.returncode != 0 and not hataya_izin:
        raise SystemExit(f"Komut basarisiz ({' '.join(argv)}):\n{sonuc.stdout}\n{sonuc.stderr}")
    return sonuc.stdout


def konteyner_durumu(ad: str) -> dict:
    """Konteynerin calisip calismadigi, cikis kodu ve yeniden baslama sayisi."""
    cikti = komut([
        "docker", "inspect", ad,
        "--format", "{{.State.Running}}|{{.State.ExitCode}}|{{.RestartCount}}|{{.State.StartedAt}}",
    ], hataya_izin=True).strip()
    if not cikti:
        return {"calisiyor": False, "cikis_kodu": None, "yeniden_baslama": None, "baslama": ""}
    calisiyor, kod, sayi, baslama = cikti.split("|")
    return {
        "calisiyor": calisiyor == "true",
        "cikis_kodu": int(kod),
        "yeniden_baslama": int(sayi),
        "baslama": baslama,
    }


def django_sorgusu(kod: str) -> dict:
    """Calisan isci konteynerinde tek seferlik bir Django sorgusu kosar."""
    tam = (
        "import json, django, os;"
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE','gozcu_api.settings');"
        "django.setup();" + kod
    )
    cikti = komut(["docker", "compose", "exec", "-T", "worker", "python", "-c", tam])
    return json.loads(cikti.strip().splitlines()[-1])


def durum_ozeti(gorev_id: int, kosu_id: int) -> dict:
    """Kare durumlari, tespit sayilari ve yinelenen tespit denetimi."""
    return django_sorgusu(
        "from django.db.models import Count;"
        "from core.models import Detection, Frame, InferenceRun;"
        f"durumlar = dict(Frame.objects.filter(mission_id={gorev_id}).values_list('status')"
        ".annotate(sayi=Count('id')));"
        f"kosu = InferenceRun.objects.get(pk={kosu_id});"
        f"yinelenen = (Detection.objects.filter(inference_run_id={kosu_id})"
        ".values('frame_id','x1','y1','x2','y2','score').annotate(sayi=Count('id'))"
        ".filter(sayi__gt=1).count());"
        "print(json.dumps({'durumlar': durumlar,"
        f"'frame_sayisi': Frame.objects.filter(mission_id={gorev_id}).count(),"
        f"'tespit_sayisi': Detection.objects.filter(inference_run_id={kosu_id}).count(),"
        "'yinelenen_tespit': yinelenen, 'kosu_durumu': kosu.status,"
        "'frames_done': kosu.frames_done, 'frames_failed': kosu.frames_failed,"
        "'frames_total': kosu.frames_total}))"
    )


def isleme_gecen_kare(gorev_id: int) -> dict | None:
    """Su anda processing durumunda olan ilk kare."""
    sonuc = django_sorgusu(
        "from core.models import Frame;"
        f"k = Frame.objects.filter(mission_id={gorev_id}, status='processing')"
        ".order_by('id').first();"
        "print(json.dumps({'frame_id': k.id, 'durum': k.status} if k else {}))"
    )
    return sonuc or None


def kare_durumu(frame_id: int) -> str:
    """Tek bir karenin su anki durumu."""
    return django_sorgusu(
        "from core.models import Frame;"
        f"print(json.dumps({{'durum': Frame.objects.get(pk={frame_id}).status}}))"
    )["durum"]


def kosuyu_hazirla(arg: argparse.Namespace, gorev_adi: str) -> dict:
    """Gorev, kareler ve kosu kaydini olusturur; kuyruga HENUZ birakmaz."""
    cikti = komut([
        "docker", "compose", "run", "--rm", "-T",
        "-v", f"{arg.goruntu_dizini.resolve()}:{arg.konteyner_dizini}:ro",
        arg.isci_servisi.replace("worker", "web"), "python", "manage.py", "olcum_kosusu",
        "--goruntu-dizini", arg.konteyner_dizini,
        "--gorev-adi", gorev_adi,
        "--model-surumu", arg.model_surumu,
        "--limit", str(arg.kare_sayisi),
        "--baslatma", "bekle",
    ])
    for satir in reversed(cikti.strip().splitlines()):
        if satir.startswith("{"):
            return json.loads(satir)
    raise SystemExit(f"Hazirlik JSON ozeti dondurmedi:\n{cikti}")


def kuyruga_birak(kosu_id: int) -> None:
    """Kosuyu gercek kuyruga birakir; isi calisan isci yapar."""
    django_sorgusu(
        "from core.tasks import run_inference;"
        f"run_inference.delay({kosu_id});"
        "print(json.dumps({'kuyruga_birakildi': True}))"
    )


def tekrar_islenen_kareler(yol: Path, kosu_id: int) -> dict:
    """Zamanlama kaydindan bu kosuda birden fazla kez islenen kareler."""
    if not yol.is_file():
        return {}
    sayim: dict[int, int] = {}
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir:
            continue
        kayit = json.loads(satir)
        if kayit.get("run_id") == kosu_id:
            sayim[kayit["frame_id"]] = sayim.get(kayit["frame_id"], 0) + 1
    return {kare: sayi for kare, sayi in sayim.items() if sayi > 1}


# --- Kapi ---------------------------------------------------------------------


def kapi_kontrolleri(olcum: dict) -> list[dict]:
    """C kapisinin butun kosullari; hepsi gecmeden kapi acilmaz."""
    return [
        {"kontrol": "isci gercekten SIGKILL ile olduruldu",
         "beklenen": f"cikis {SIGKILL_CIKIS_KODU} veya yeniden baslama artisi",
         "olculen": olcum["sigkill_kaniti"],
         "sonuc": "GECTI" if olcum["sigkill_dogrulandi"] else "GECMEDI"},
        {"kontrol": "gorev yeniden teslim edildi (oldurulen kare bitti)",
         "beklenen": "evet", "olculen": olcum["yeniden_teslim"],
         "sonuc": "GECTI" if olcum["yeniden_teslim"] == "evet" else "GECMEDI"},
        {"kontrol": "oldurulen karenin son durumu", "beklenen": "done",
         "olculen": olcum["oldurulen_kare_son_durumu"],
         "sonuc": "GECTI" if olcum["oldurulen_kare_son_durumu"] == "done" else "GECMEDI"},
        {"kontrol": "butun kareler son duruma ulasti", "beklenen": olcum["toplam_frame"],
         "olculen": olcum["done_frame"] + olcum["failed_frame"],
         "sonuc": "GECTI" if olcum["done_frame"] + olcum["failed_frame"] == olcum["toplam_frame"] else "GECMEDI"},
        {"kontrol": "kayip kare", "beklenen": 0, "olculen": olcum["kayip_frame"],
         "sonuc": "GECTI" if olcum["kayip_frame"] == 0 else "GECMEDI"},
        {"kontrol": "takili kare (pending/queued/processing)", "beklenen": 0,
         "olculen": olcum["takili_frame"],
         "sonuc": "GECTI" if olcum["takili_frame"] == 0 else "GECMEDI"},
        {"kontrol": "kontrolsuz yinelenen Detection", "beklenen": 0,
         "olculen": olcum["yinelenen_tespit"],
         "sonuc": "GECTI" if olcum["yinelenen_tespit"] == 0 else "GECMEDI"},
        {"kontrol": "CSV tespit toplami = veritabani", "beklenen": olcum["toplam_detection"],
         "olculen": olcum["toplam_detection_db"],
         "sonuc": "GECTI" if olcum["toplam_detection"] == olcum["toplam_detection_db"] else "GECMEDI"},
        {"kontrol": "gercek ONNX dedektoru", "beklenen": "onnx",
         "olculen": olcum["model_cercevesi"],
         "sonuc": "GECTI" if olcum["model_cercevesi"] == "onnx" else "GECMEDI"},
        {"kontrol": "model sha256", "beklenen": olcum["model_sha256_kayit"],
         "olculen": olcum["model_sha256"],
         "sonuc": "GECTI" if olcum["model_sha256"] == olcum["model_sha256_kayit"] else "GECMEDI"},
        {"kontrol": "kosu son duruma ulasti", "beklenen": "done",
         "olculen": olcum["kosu_durumu"],
         "sonuc": "GECTI" if olcum["kosu_durumu"] == "done" else "GECMEDI"},
    ]


def main() -> None:
    arg = argumanlari_coz()
    baslangic_zamani = datetime.now()
    baslangic = time.perf_counter()

    kayit = list(csv.DictReader((RAPOR_KOK / "model512_onnx_bilgisi.csv").open(encoding="utf-8")))[0]
    model_sha = KIMLIK.dosya_sha256(MODEL_YOLU)
    if model_sha != kayit["onnx_sha256"]:
        raise SystemExit(
            f"Model SHA-256 uyusmuyor (disk {model_sha}, kayit {kayit['onnx_sha256']}). "
            "Test calistirilmadi."
        )

    ayarlar = SURE.servis_ayarlari()
    isci = konteyner_durumu(arg.isci_konteyneri)
    if not isci["calisiyor"]:
        raise SystemExit(f"Isci konteyneri calismiyor: {arg.isci_konteyneri}")
    redis = konteyner_durumu("gozcu_redis")
    if not redis["calisiyor"]:
        raise SystemExit("Redis calismiyor; test baslatilmadi.")

    print(f"Model SHA-256 UYUSTU: {model_sha[:16]}...")
    print(f"Ayarlar: soft {ayarlar['soft_limit']} | hard {ayarlar['hard_limit']} | "
          f"visibility {ayarlar['visibility_timeout']} | acks_late {ayarlar['acks_late']} | "
          f"prefetch {ayarlar['prefetch']}")

    gorev_adi = arg.gorev_adi or f"sigkill-dayaniklilik-{baslangic_zamani:%Y%m%d-%H%M%S}"
    hazirlik = kosuyu_hazirla(arg, gorev_adi)
    print(f"\nGorev: {gorev_adi} (id {hazirlik['gorev_id']}) | kosu {hazirlik['kosu_id']} | "
          f"{hazirlik['kare_sayisi']} kare")

    onceki_zamanlama = tekrar_islenen_kareler(arg.zamanlama_log_host, hazirlik["kosu_id"])
    baslangic_durumu = durum_ozeti(hazirlik["gorev_id"], hazirlik["kosu_id"])
    print(f"Baslangic durumlari: {baslangic_durumu['durumlar']} | "
          f"tespit {baslangic_durumu['tespit_sayisi']}")

    kuyruga_birak(hazirlik["kosu_id"])
    print("Kosu gercek kuyruga birakildi; isci isliyor...", flush=True)

    # 1) En az bir kare processing olana kadar bekle.
    islenen = None
    bekleme_basi = time.perf_counter()
    while time.perf_counter() - bekleme_basi < arg.islem_bekleme:
        islenen = isleme_gecen_kare(hazirlik["gorev_id"])
        if islenen:
            break
        time.sleep(arg.yoklama_araligi)
    if not islenen:
        raise SystemExit(
            "Hicbir kare processing durumuna gecmedi; isci calismiyor olabilir. "
            "SIGKILL gonderilmedi."
        )
    kill_oncesi = durum_ozeti(hazirlik["gorev_id"], hazirlik["kosu_id"])
    print(f"Isleniyor: frame {islenen['frame_id']} | o andaki tespit "
          f"{kill_oncesi['tespit_sayisi']}", flush=True)

    # 2) SIGKILL. Graceful stop kullanilmaz.
    kill_oncesi_konteyner = konteyner_durumu(arg.isci_konteyneri)
    kill_zamani = time.perf_counter()
    komut(["docker", "kill", "--signal=KILL", arg.isci_konteyneri])
    print(f"SIGKILL gonderildi: {arg.isci_konteyneri}", flush=True)

    # 3) Oldugunu dogrula: ya durmus ve 137 ile cikmis, ya da yeniden baslatilmis.
    sigkill_dogrulandi = False
    kanit = ""
    for _ in range(20):
        durum = konteyner_durumu(arg.isci_konteyneri)
        if durum["cikis_kodu"] == SIGKILL_CIKIS_KODU and not durum["calisiyor"]:
            sigkill_dogrulandi = True
            kanit = f"cikis kodu {durum['cikis_kodu']}, konteyner durmus"
            break
        if durum["yeniden_baslama"] is not None and kill_oncesi_konteyner["yeniden_baslama"] is not None \
                and durum["yeniden_baslama"] > kill_oncesi_konteyner["yeniden_baslama"]:
            sigkill_dogrulandi = True
            kanit = (f"yeniden baslama sayaci {kill_oncesi_konteyner['yeniden_baslama']} -> "
                     f"{durum['yeniden_baslama']}, cikis kodu {durum['cikis_kodu']}")
            break
        time.sleep(1.0)
    if not sigkill_dogrulandi:
        raise SystemExit(
            "Isci konteynerinin olduğu dogrulanamadi; test devam etmiyor. "
            f"Son durum: {konteyner_durumu(arg.isci_konteyneri)}"
        )
    print(f"SIGKILL dogrulandi: {kanit}", flush=True)

    # 4) Ayni isci hizmetini yeniden baslat (restart politikasi zaten baslatmis olabilir).
    komut(["docker", "compose", "up", "-d", arg.isci_servisi])
    yeniden_baslama_suresi = time.perf_counter() - kill_zamani
    isci_sonrasi = konteyner_durumu(arg.isci_konteyneri)
    print(f"Isci ayakta: calisiyor={isci_sonrasi['calisiyor']} "
          f"({sayi_bicimle(yeniden_baslama_suresi, 1)} sn sonra)", flush=True)

    # 5) Yeniden teslim ve bitis. Ust sinir visibility + hard limit + pay.
    pay = arg.teslim_payi or ayarlar["hard_limit"]
    ust_sinir = ayarlar["visibility_timeout"] + ayarlar["hard_limit"] + pay
    print(f"Yeniden teslim bekleniyor (ust sinir {ust_sinir} sn = visibility "
          f"{ayarlar['visibility_timeout']} + hard {ayarlar['hard_limit']} + pay {pay})",
          flush=True)

    # OLCULEN SEY: OLDURULEN karenin kendisinin son duruma ulasmasi. Baska bir
    # karenin bitmesi yeniden teslim degildir; ilk surumde bu karistigi icin
    # sure olcumu yanlis olaya baglanmisti.
    teslim_suresi = None
    oldurulen_kare_durumu = islenen["durum"]
    son = None
    bekleme_basi = time.perf_counter()
    while time.perf_counter() - bekleme_basi < ust_sinir:
        son = durum_ozeti(hazirlik["gorev_id"], hazirlik["kosu_id"])
        takili = sum(sayi for durum, sayi in son["durumlar"].items() if durum in TAKILI_DURUMLAR)
        if teslim_suresi is None:
            oldurulen_kare_durumu = kare_durumu(islenen["frame_id"])
            if oldurulen_kare_durumu in SON_DURUMLAR:
                teslim_suresi = time.perf_counter() - kill_zamani
        if takili == 0:
            break
        gecen = time.perf_counter() - bekleme_basi
        print(f"  bekleniyor {sayi_bicimle(gecen, 0)} sn | durumlar {son['durumlar']}",
              flush=True)
        time.sleep(max(arg.yoklama_araligi, 15.0))

    son = durum_ozeti(hazirlik["gorev_id"], hazirlik["kosu_id"])
    tekrar_islenen = tekrar_islenen_kareler(arg.zamanlama_log_host, hazirlik["kosu_id"])
    bitis_zamani = datetime.now()
    toplam_sure = time.perf_counter() - baslangic

    done = son["durumlar"].get("done", 0)
    failed = son["durumlar"].get("failed", 0)
    takili = sum(sayi for durum, sayi in son["durumlar"].items() if durum in TAKILI_DURUMLAR)

    olcum = {
        "test_baslangici": baslangic_zamani.strftime("%Y-%m-%d %H:%M:%S"),
        "test_bitisi": bitis_zamani.strftime("%Y-%m-%d %H:%M:%S"),
        "gorev_adi": gorev_adi,
        "gorev_id": hazirlik["gorev_id"],
        "kosu_id": hazirlik["kosu_id"],
        "model_surumu": hazirlik["model_surumu"],
        "model_cercevesi": hazirlik["model_cercevesi"],
        "model_sha256": model_sha,
        "model_sha256_kayit": kayit["onnx_sha256"],
        "isci_konteyneri": arg.isci_konteyneri,
        "toplam_frame": son["frame_sayisi"],
        "sigkill_aninda_frame": islenen["frame_id"],
        "sigkill_aninda_frame_durumu": islenen["durum"],
        "sigkill_aninda_tespit": kill_oncesi["tespit_sayisi"],
        "sigkill_kaniti": kanit,
        "sigkill_dogrulandi": sigkill_dogrulandi,
        "isci_yeniden_baslama_suresi": sayi_bicimle(yeniden_baslama_suresi, 2),
        "isci_yeniden_baslama_zamani": isci_sonrasi["baslama"],
        "yeniden_teslim": "evet" if teslim_suresi is not None else "hayir",
        "yeniden_teslim_suresi": sayi_bicimle(teslim_suresi, 2) if teslim_suresi else "olculmedi",
        "yeniden_teslim_olcumu": (
            "SIGKILL anindaki karenin kendisinin son duruma ulasma suresi "
            "(baska karelerin bitisi sayilmaz)"
        ),
        "oldurulen_kare_son_durumu": oldurulen_kare_durumu,
        "done_frame": done,
        "failed_frame": failed,
        "pending_frame": son["durumlar"].get("pending", 0),
        "queued_frame": son["durumlar"].get("queued", 0),
        "processing_frame": son["durumlar"].get("processing", 0),
        "takili_frame": takili,
        "kayip_frame": son["frame_sayisi"] - (done + failed + takili),
        "tekrar_islenen_frame": len(tekrar_islenen),
        "tekrar_islenen_olcumu": (
            "zamanlama kaydinda birden fazla satiri olan kareler; SIGKILL ile olen "
            "deneme is ortasinda oldugu icin kayit yazamaz, bu yuzden yeniden teslim "
            "edilen kare burada gorunmeyebilir"
        ),
        "tekrar_islenen_frame_listesi": ";".join(str(k) for k in sorted(tekrar_islenen)),
        "yinelenen_tespit": son["yinelenen_tespit"],
        "toplam_detection": son["tespit_sayisi"],
        "toplam_detection_db": son["tespit_sayisi"],
        "kosu_durumu": son["kosu_durumu"],
        "kosu_frames_done": son["frames_done"],
        "kosu_frames_failed": son["frames_failed"],
        "toplam_test_suresi": sayi_bicimle(toplam_sure, 2),
        "soft_limit": ayarlar["soft_limit"],
        "hard_limit": ayarlar["hard_limit"],
        "visibility_timeout": ayarlar["visibility_timeout"],
        "acks_late": ayarlar["acks_late"],
        "prefetch": ayarlar["prefetch"],
        "yeniden_teslim_ust_siniri": ust_sinir,
    }

    kontrol = kapi_kontrolleri(olcum)
    gecti = all(s["sonuc"] == "GECTI" for s in kontrol)
    olcum["kapi_sonucu"] = "GECTI" if gecti else "GECMEDI"

    print("\n=== C KAPISI KONTROLLERI ===")
    tablo_bas(kontrol)

    kosu = kosu_bilgisi(
        gorev_adi=gorev_adi,
        model_surumu=hazirlik["model_surumu"],
        onnx_sha256=model_sha,
        onnx_model_yolu=ayarlar["onnx_model_path"],
        oldurme_yontemi=f"docker kill --signal=KILL {arg.isci_konteyneri} (graceful stop degil)",
        olcum_yolu="gercek Celery kuyrugu; gorev fonksiyonu dogrudan cagrilmadi",
        onceki_tekrar_islenen=";".join(str(k) for k in sorted(onceki_zamanlama)) or "yok",
    )
    cikti = csv_yaz(arg.cikti, [olcum], kosu)
    print(f"\nCSV: {cikti}")
    print(f"\nC KAPISI: {olcum['kapi_sonucu']}")
    if not gecti:
        sys.exit(1)


if __name__ == "__main__":
    main()
