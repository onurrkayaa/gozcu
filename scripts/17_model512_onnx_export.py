"""Model-512 agirligini ONNX bicimine aktarir ve olusan dosyanin kimligini kaydeder.

YALNIZCA EXPORT VE YAPISAL DOGRULAMA. ONNX uzerinde tahmin calistirilmaz,
PyTorch-ONNX ciktilari karsilastirilmaz, hiz/recall/FP olculmez. Bunlar sonraki
adimin isidir.

Kaynak kimligi (boyut, SHA-256, sinif adlari) rapordan degil DISKTEN okunur ve
Kaggle kosusundaki ozgun best.pt ile karsilastirilir. Giris boyutu egitim
kaydindaki args.yaml'dan gelir.

Otomatik paket kurulumu kapalidir (YOLO_AUTOINSTALL=false): eksik bir paket
varsa Ultralytics sessizce ag uzerinden kurmak yerine hata verir.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ultralytics'ten ONCE ayarlanmali: eksik bagimlilik sessizce kurulmasin.
os.environ.setdefault("YOLO_AUTOINSTALL", "false")

import importlib.util  # noqa: E402

SCRIPT_DIZIN = Path(__file__).resolve().parent
PROJE_KOK = SCRIPT_DIZIN.parent
sys.path.insert(0, str(SCRIPT_DIZIN))

from ortak import RAPOR_KOK, csv_yaz, kosu_bilgisi, tablo_bas  # noqa: E402


def _modul_yukle(ad: str, dosya: str):
    """Rakamla baslayan script dosyalarini yoldan yukler."""
    spec = importlib.util.spec_from_file_location(ad, SCRIPT_DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# Dosya baytlarindan SHA-256: 14'te yazildi, burada yeniden yazilmaz.
KIMLIK = _modul_yukle("asinalik", "14_egitim_test_asinalik.py")

VARSAYILAN_PT = PROJE_KOK / "agirliklar" / "model512_best.pt"
EGITIM_CIKTI_KOK = PROJE_KOK / "egitim" / "kaggle_cikti"
ARGS_YAML_DESENI = "**/model512/args.yaml"

# Export ayarlari. Hicbiri varsayilana birakilmadi; hepsi acikca verilir ve
# olusan grafikten geri okunur.
EXPORT_FORMAT = "onnx"
EXPORT_BATCH = 1          # cikarim tek goruntuyle yapiliyor; args.yaml'daki 16 EGITIM batch'idir
EXPORT_DYNAMIC = False
EXPORT_SIMPLIFY = True
EXPORT_HALF = False
EXPORT_DEVICE = "cpu"

ZORUNLU_PAKETLER = ("onnx", "onnxslim", "onnxruntime", "ultralytics", "torch")


def argumanlari_coz() -> argparse.Namespace:
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Model-512 agirligini ONNX'e aktarir ve yapisal olarak dogrular. "
            "Tahmin calistirmaz, hiz olcmez."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--pt", type=Path, default=VARSAYILAN_PT, help="Kaynak agirlik dosyasi")
    ayrastirici.add_argument(
        "--egitim-cikti", type=Path, default=EGITIM_CIKTI_KOK,
        help="Kaggle kosu ciktisinin kok klasoru; args.yaml ve ozgun best.pt burada aranir",
    )
    ayrastirici.add_argument(
        "--onnx", type=Path, default=None,
        help="Cikti ONNX yolu (varsayilan: kaynak .pt ile ayni klasor, .onnx uzantili)",
    )
    ayrastirici.add_argument(
        "--cikti", type=Path, default=RAPOR_KOK / "model512_onnx_bilgisi.csv",
        help="Sonuc CSV dosyasinin yolu",
    )
    return ayrastirici.parse_args()


# --- Bagimlilik kapisi --------------------------------------------------------


def paket_surumleri(paketler=ZORUNLU_PAKETLER) -> dict[str, str]:
    """Zorunlu paketlerin surumlerini dondurur; biri eksikse ImportError yukselir."""
    surumler = {}
    for ad in paketler:
        modul = __import__(ad)
        surumler[ad] = getattr(modul, "__version__", "bilinmiyor")
    return surumler


# --- Kaynak kimligi -----------------------------------------------------------


def dosya_kimligi(yol: Path) -> dict:
    """Bir dosyanin yolunu, boyutunu ve SHA-256 ozetini dondurur."""
    if not yol.is_file():
        raise FileNotFoundError(f"Dosya bulunamadi: {yol}")
    return {
        "yol": yol.as_posix(),
        "boyut_bayt": yol.stat().st_size,
        "sha256": KIMLIK.dosya_sha256(yol),
    }


def args_yaml_bul(egitim_cikti: Path, desen: str = ARGS_YAML_DESENI) -> Path:
    """Egitim kaydindaki args.yaml'i arayarak bulur; tek aday olmali."""
    adaylar = sorted(egitim_cikti.glob(desen))
    if not adaylar:
        raise SystemExit(f"args.yaml bulunamadi: {egitim_cikti}/{desen}")
    if len(adaylar) > 1:
        raise SystemExit(
            "Birden fazla args.yaml adayi var, hangisinin kullanilacagi belirsiz: "
            + ", ".join(a.as_posix() for a in adaylar)
        )
    return adaylar[0]


def args_oku(args_yaml: Path) -> dict:
    """Egitim argumanlarini okur."""
    import yaml

    return yaml.safe_load(args_yaml.read_text(encoding="utf-8"))


def ozgun_agirlikla_karsilastir(kaynak: dict, egitim_cikti: Path) -> dict:
    """Kaggle kosusundaki ozgun best.pt ile SHA-256 karsilastirmasi.

    Ozgun dosya yoksa karsilastirma yapilamaz; bu bir hata degildir ama
    durumu acikca kaydedilir."""
    adaylar = sorted(egitim_cikti.glob("**/model512/weights/best.pt"))
    if not adaylar:
        return {"durum": "ozgun best.pt bulunamadi", "yol": "", "sha256": ""}
    if len(adaylar) > 1:
        raise SystemExit(
            "Birden fazla ozgun best.pt adayi var: "
            + ", ".join(a.as_posix() for a in adaylar)
        )
    ozgun = dosya_kimligi(adaylar[0])
    return {
        "durum": "UYUSTU" if ozgun["sha256"] == kaynak["sha256"] else "UYUSMADI",
        "yol": ozgun["yol"],
        "sha256": ozgun["sha256"],
    }


def pt_model_bilgisi(pt_yolu: Path) -> dict:
    """Agirlik dosyasindan sinif adlarini ve kayitli giris boyutunu okur."""
    from ultralytics import YOLO

    model = YOLO(str(pt_yolu))
    adlar = model.names
    return {
        "model": model,
        "sinif_adlari": ";".join(f"{no}:{ad}" for no, ad in sorted(adlar.items())),
    }


# --- Export -------------------------------------------------------------------


def secilen_opset() -> int:
    """Kurulu Ultralytics'in bu torch surumu icin sectigi opset degeri."""
    import onnx
    from ultralytics.utils.export.engine import best_onnx_opset

    return best_onnx_opset(onnx)


def onnx_export_et(model, imgsz: int, opset: int) -> Path:
    """Ultralytics ile ONNX export. Ayarlarin hicbiri varsayilana birakilmaz."""
    yol = model.export(
        format=EXPORT_FORMAT,
        imgsz=imgsz,
        batch=EXPORT_BATCH,
        opset=opset,
        dynamic=EXPORT_DYNAMIC,
        simplify=EXPORT_SIMPLIFY,
        half=EXPORT_HALF,
        device=EXPORT_DEVICE,
    )
    return Path(yol)


# --- Yapisal dogrulama --------------------------------------------------------


def _sekil(deger) -> str:
    """Tensor sekli; sabit boyutlar sayi, dinamik boyutlar ad olarak yazilir."""
    parcalar = []
    for boyut in deger.type.tensor_type.shape.dim:
        if boyut.HasField("dim_value"):
            parcalar.append(str(boyut.dim_value))
        elif boyut.dim_param:
            parcalar.append(boyut.dim_param)
        else:
            parcalar.append("?")
    return "x".join(parcalar)


def onnx_yapisal_dogrula(onnx_yolu: Path) -> dict:
    """ONNX dosyasini acar, checker'dan gecirir ve grafik metadata'sini okur.

    Bu bir INFERENCE DEGILDIR: ONNX Runtime oturumu acilmaz, tensor beslenmez."""
    import onnx

    if not onnx_yolu.is_file():
        raise FileNotFoundError(f"ONNX dosyasi olusmadi: {onnx_yolu}")
    if onnx_yolu.stat().st_size == 0:
        raise ValueError(f"ONNX dosyasi bos: {onnx_yolu}")

    model = onnx.load(str(onnx_yolu))
    onnx.checker.check_model(model)

    opsetler = [f"{o.domain or 'ai.onnx'}:{o.version}" for o in model.opset_import]
    varsayilan = [o.version for o in model.opset_import if o.domain in ("", "ai.onnx")]

    def tur(deger) -> str:
        return onnx.TensorProto.DataType.Name(deger.type.tensor_type.elem_type)

    return {
        "checker_durumu": "GECTI",
        "opset": varsayilan[0] if varsayilan else "olculmedi",
        "opset_tumu": ";".join(opsetler),
        "girdi_adlari": ";".join(g.name for g in model.graph.input),
        "girdi_sekilleri": ";".join(f"{g.name}:{_sekil(g)}" for g in model.graph.input),
        "girdi_veri_turleri": ";".join(f"{g.name}:{tur(g)}" for g in model.graph.input),
        "cikti_adlari": ";".join(c.name for c in model.graph.output),
        "cikti_sekilleri": ";".join(f"{c.name}:{_sekil(c)}" for c in model.graph.output),
        "cikti_veri_turleri": ";".join(f"{c.name}:{tur(c)}" for c in model.graph.output),
    }


# --- CSV ----------------------------------------------------------------------


def olcum_satiri(kaynak: dict, sinif_adlari: str, args_yaml: Path, ozgun: dict,
                 onnx_kimlik: dict, yapi: dict, imgsz: int, opset: int) -> dict:
    """CSV'ye yazilacak tek olcum satiri."""
    return {
        "kaynak_pt": kaynak["yol"],
        "kaynak_pt_boyut_bayt": kaynak["boyut_bayt"],
        "kaynak_pt_sha256": kaynak["sha256"],
        "kaynak_sinif_adlari": sinif_adlari,
        "ozgun_best_pt": ozgun["yol"],
        "ozgun_best_pt_sha256": ozgun["sha256"],
        "ozgun_best_pt_eslesmesi": ozgun["durum"],
        "args_yaml": args_yaml.as_posix(),
        "onnx_dosyasi": onnx_kimlik["yol"],
        "onnx_boyut_bayt": onnx_kimlik["boyut_bayt"],
        "onnx_sha256": onnx_kimlik["sha256"],
        "onnx_opset": yapi["opset"],
        "onnx_opset_tumu": yapi["opset_tumu"],
        "onnx_girdi_adlari": yapi["girdi_adlari"],
        "onnx_girdi_sekilleri": yapi["girdi_sekilleri"],
        "onnx_girdi_veri_turleri": yapi["girdi_veri_turleri"],
        "onnx_cikti_adlari": yapi["cikti_adlari"],
        "onnx_cikti_sekilleri": yapi["cikti_sekilleri"],
        "onnx_cikti_veri_turleri": yapi["cikti_veri_turleri"],
        "export_format": EXPORT_FORMAT,
        "export_imgsz": imgsz,
        "export_batch": EXPORT_BATCH,
        "export_opset": opset,
        "export_dynamic": EXPORT_DYNAMIC,
        "export_simplify": EXPORT_SIMPLIFY,
        "export_half": EXPORT_HALF,
        "export_device": EXPORT_DEVICE,
        "onnx_checker_durumu": yapi["checker_durumu"],
    }


def main() -> None:
    arg = argumanlari_coz()

    try:
        surumler = paket_surumleri()
    except ImportError as hata:
        raise SystemExit(
            f"Zorunlu paket eksik: {hata.name}. Otomatik kurulum kapali; "
            f"kurulum icin: .venv/bin/python -m pip install {hata.name}"
        ) from hata
    print("Paketler: " + " | ".join(f"{a} {s}" for a, s in surumler.items()))
    print(f"Otomatik kurulum: kapali (YOLO_AUTOINSTALL={os.environ['YOLO_AUTOINSTALL']})")

    kaynak = dosya_kimligi(arg.pt)
    ozgun = ozgun_agirlikla_karsilastir(kaynak, arg.egitim_cikti)
    if ozgun["durum"] == "UYUSMADI":
        print(f"\nKaynak {kaynak['sha256']}\nOzgun  {ozgun['sha256']}")
        raise SystemExit(
            "KAPI GECMEDI: kaynak .pt, egitim ciktisindaki ozgun best.pt ile "
            "ayni dosya degil. Export yapilmadi."
        )

    args_yaml = args_yaml_bul(arg.egitim_cikti)
    egitim_args = args_oku(args_yaml)
    imgsz = int(egitim_args["imgsz"])
    bilgi = pt_model_bilgisi(arg.pt)

    print(f"\nKaynak .pt : {kaynak['yol']}")
    print(f"  boyut    : {kaynak['boyut_bayt']} bayt")
    print(f"  sha256   : {kaynak['sha256']}")
    print(f"  siniflar : {bilgi['sinif_adlari']}")
    print(f"  ozgun best.pt eslesmesi: {ozgun['durum']} ({ozgun['yol'] or 'yok'})")
    print(f"args.yaml  : {args_yaml.as_posix()}  (imgsz {imgsz}, egitim batch "
          f"{egitim_args.get('batch')})")

    opset = secilen_opset()
    print(f"\nExport: format {EXPORT_FORMAT} | imgsz {imgsz} | batch {EXPORT_BATCH} | "
          f"opset {opset} | dynamic {EXPORT_DYNAMIC} | simplify {EXPORT_SIMPLIFY} | "
          f"half {EXPORT_HALF} | device {EXPORT_DEVICE}", flush=True)

    uretilen = onnx_export_et(bilgi["model"], imgsz, opset)
    hedef = arg.onnx or arg.pt.with_suffix(".onnx")
    if uretilen.resolve() != hedef.resolve():
        uretilen.replace(hedef)
    onnx_kimlik = dosya_kimligi(hedef)

    yapi = onnx_yapisal_dogrula(hedef)

    satir = olcum_satiri(
        kaynak, bilgi["sinif_adlari"], args_yaml, ozgun, onnx_kimlik, yapi, imgsz, opset
    )
    kosu = kosu_bilgisi(
        kaynak_script="scripts/17_model512_onnx_export.py",
        kapsam_notu=(
            "yalnizca export ve yapisal dogrulama; ONNX Runtime oturumu acilmadi, "
            "tahmin calistirilmadi, hiz/recall/FP olculmedi"
        ),
        opset_secimi="ultralytics.utils.export.engine.best_onnx_opset",
        imgsz_kaynagi=args_yaml.as_posix(),
        otomatik_kurulum="kapali (YOLO_AUTOINSTALL=false)",
        surum_onnx=surumler["onnx"],
        surum_onnxruntime=surumler["onnxruntime"],
        surum_onnxslim=surumler["onnxslim"],
    )
    cikti = csv_yaz(arg.cikti, [satir], kosu)

    print("\n=== ONNX ===")
    tablo_bas([{
        "onnx": onnx_kimlik["yol"],
        "boyut_bayt": onnx_kimlik["boyut_bayt"],
        "opset": yapi["opset"],
        "checker": yapi["checker_durumu"],
    }])
    print(f"  sha256  : {onnx_kimlik['sha256']}")
    print(f"  girdi   : {yapi['girdi_sekilleri']} ({yapi['girdi_veri_turleri']})")
    print(f"  cikti   : {yapi['cikti_sekilleri']} ({yapi['cikti_veri_turleri']})")
    print(f"\nCSV: {cikti}")
    print("\nKAPI GECTI: kaynak kimligi dogrulandi, ONNX olustu, checker gecti, "
          "opset ve girdi/cikti metadata'si okundu. Inference calistirilmadi.")


if __name__ == "__main__":
    main()
