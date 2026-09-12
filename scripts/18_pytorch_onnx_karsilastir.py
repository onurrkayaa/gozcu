"""PyTorch ve ONNX Runtime motorlarini AYNI protokolde karsilastirir.

Degisen TEK sey cikarim motorudur. Goruntuler, SAHI karolamasi, karo boyutu,
ortusme, karolar arasi NMS, koordinat tasima, IoU esigi, gercek kutu
eslestirmesi ve metrik hesabi iki tarafta da ayni koddur:

    PyTorch: ortak.model_kur (SAHI + Ultralytics .pt)   <- mevcut olcum yolu
    ONNX   : backend/core/onnx_detector.py               <- Celery'de calisacak motor

ONNX tarafinda Ultralytics'in ONNX sarmalayicisi DEGIL, backend'in kendi
onnxruntime dedektoru olculur. Sebep: sonraki adimda Celery iscisinde calisacak
motor budur ve "olculen motor ile uretimde calisan motor ayni olmali" kurali
ancak boyle saglanir. Bu modul SAHI'ye yalnizca karo bazinda cikarim saglayan
ince bir sarmalayiciyla baglanir; dilimleme, kaydirma ve karolar arasi son islem
SAHI'nin kendi kodunda kalir.

Protokol degerleri (model, karo, ortusme, IoU, esikler, cihaz) bu dosyaya
yazilmaz; reports/test_model512.csv'nin kosu_ sutunlarindan okunur.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

SCRIPT_DIZIN = Path(__file__).resolve().parent
PROJE_KOK = SCRIPT_DIZIN.parent
sys.path.insert(0, str(SCRIPT_DIZIN))
sys.path.insert(0, str(PROJE_KOK / "backend"))

import importlib.util  # noqa: E402

from ortak import (  # noqa: E402
    RAPOR_KOK,
    VERI_KOK,
    Kutu,
    bolum_yolu,
    csv_yaz,
    esikte_degerlendir,
    gercekleri_yukle,
    goruntuleri_listele,
    karolamali_tara,
    kosu_bilgisi,
    kutulari_eslestir,
    model_kur,
    sayi_bicimle,
    tablo_bas,
)

from core.onnx_detector import OnnxDedektor  # noqa: E402


def _modul_yukle(ad: str, dosya: str):
    spec = importlib.util.spec_from_file_location(ad, SCRIPT_DIZIN / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# Dosya baytlarindan SHA-256: 14'te yazildi, burada yeniden yazilmaz.
KIMLIK = _modul_yukle("asinalik", "14_egitim_test_asinalik.py")

VARSAYILAN_OLCUM = RAPOR_KOK / "test_model512.csv"
VARSAYILAN_ONNX_BILGI = RAPOR_KOK / "model512_onnx_bilgisi.csv"

MOTORLAR = ("pytorch", "onnx")
OZET_SATIRI = "TOPLAM"


def argumanlari_coz() -> argparse.Namespace:
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Ayni protokolde PyTorch ve ONNX Runtime motorlarini karsilastirir. "
            "Protokol degerleri mevcut olcum CSV'sinden okunur."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument("--veri", type=Path, default=VERI_KOK, help="Veri kumesi kok klasoru")
    ayrastirici.add_argument(
        "--olcum", type=Path, default=VARSAYILAN_OLCUM,
        help="Protokolun ve capraz kontrolun okundugu mevcut Model-512 olcumu",
    )
    ayrastirici.add_argument(
        "--onnx-bilgi", type=Path, default=VARSAYILAN_ONNX_BILGI,
        help="Export kaydi; .pt ve .onnx SHA-256 degerleri buradan dogrulanir",
    )
    ayrastirici.add_argument(
        "--fark-cikti", type=Path, default=RAPOR_KOK / "pytorch_onnx_fark.csv",
        help="Tahmin bazinda fark CSV'si",
    )
    ayrastirici.add_argument(
        "--metrik-cikti", type=Path, default=RAPOR_KOK / "pytorch_onnx_metrik.csv",
        help="Esik bazinda metrik karsilastirma CSV'si",
    )
    ayrastirici.add_argument(
        "--limit", type=int, default=0,
        help="Deneme kosusu icin en fazla kac goruntu (0 = bolumun tamami)",
    )
    return ayrastirici.parse_args()


# --- Protokol ve kaynak dogrulamasi -------------------------------------------


def protokol_oku(olcum_csv: Path) -> dict:
    """Olcum protokolunu mevcut CSV'nin kosu_ sutunlarindan okur."""
    satirlar = list(csv.DictReader(olcum_csv.open(encoding="utf-8")))
    if not satirlar:
        raise SystemExit(f"Olcum CSV'si bos: {olcum_csv}")
    ilk = satirlar[0]
    esikler = sorted(
        {float(s["conf_esigi"]) for s in satirlar if s["kaynak_onek"] == OZET_SATIRI}
    )
    if not esikler:
        raise SystemExit(f"{olcum_csv} icinde {OZET_SATIRI} satiri yok")
    return {
        "model": ilk["kosu_model"],
        "bolum": ilk["kosu_bolum"],
        "karo": int(ilk["kosu_karo_boyutu"]),
        "ortusme": float(ilk["kosu_ortusme_orani"]),
        "iou": float(ilk["kosu_iou_esigi"]),
        "cihaz": ilk["kosu_cihaz"],
        "esikler": esikler,
        "goruntu_sayisi": int(ilk["kosu_goruntu_sayisi"]),
    }


def olculen_metrikler(olcum_csv: Path) -> dict[float, dict]:
    """Mevcut olcumun TOPLAM satirlari: capraz kontrolun referansi."""
    kayit = {}
    for s in csv.DictReader(olcum_csv.open(encoding="utf-8")):
        if s["kaynak_onek"] == OZET_SATIRI:
            kayit[float(s["conf_esigi"])] = s
    return kayit


def kaynaklari_dogrula(pt_yolu: Path, onnx_yolu: Path, bilgi_csv: Path) -> dict:
    """Iki modelin SHA-256 degerini diskten hesaplar ve export kaydiyla karsilastirir."""
    kayit = list(csv.DictReader(bilgi_csv.open(encoding="utf-8")))
    if not kayit:
        raise SystemExit(f"Export kaydi bos: {bilgi_csv}")
    kayit = kayit[0]

    olculen = {
        "pt": KIMLIK.dosya_sha256(pt_yolu),
        "onnx": KIMLIK.dosya_sha256(onnx_yolu),
    }
    beklenen = {"pt": kayit["kaynak_pt_sha256"], "onnx": kayit["onnx_sha256"]}
    uyusmazlik = [ad for ad in olculen if olculen[ad] != beklenen[ad]]
    if uyusmazlik:
        for ad in uyusmazlik:
            print(f"{ad}: diskte {olculen[ad]}, kayitta {beklenen[ad]}")
        raise SystemExit(
            "Model kimligi export kaydiyla uyusmuyor. Hicbir tahmin calistirilmadi."
        )
    return olculen


# --- ONNX tarafinin SAHI'ye baglanmasi ----------------------------------------


def onnx_sahi_modeli(onnx_yolu: Path, conf: float, cihaz: str):
    """backend/core/onnx_detector.py'yi SAHI'nin bekledigi arayuze baglar.

    Yalnizca KARO BAZINDA CIKARIM degistirilir. Dilimleme, kaydirma, karolar
    arasi NMS ve ObjectPrediction uretimi SAHI'nin kendi kodunda kalir; boylece
    PyTorch kosusuyla aradaki tek fark motor olur."""
    import numpy as np
    import torch
    from sahi.models.ultralytics import UltralyticsDetectionModel

    class _SinifTasiyici:
        """SAHI kategori adlarini model nesnesinin names alanindan okur."""

        def __init__(self, adlar):
            self.names = adlar

    class OnnxRuntimeDetectionModel(UltralyticsDetectionModel):
        def load_model(self) -> None:
            self.dedektor = OnnxDedektor(self.model_path, self.confidence_threshold)
            self.set_model(_SinifTasiyici(self.dedektor.sinif_adlari))

        def perform_batch_inference(self, images) -> None:
            tahminler = []
            for goruntu in images:
                kutular = self.dedektor.karo_tahmin_et(np.ascontiguousarray(goruntu))
                # SAHI, Ultralytics Results.boxes.data bicimini bekler:
                # (x1, y1, x2, y2, skor, sinif).
                tahminler.append(
                    torch.tensor(
                        [[k[0], k[1], k[2], k[3], k[4], 0.0] for k in kutular],
                        dtype=torch.float32,
                    ).reshape(-1, 6)
                )
            self._original_predictions = tahminler
            self._original_shapes = [g.shape for g in images]

    return OnnxRuntimeDetectionModel(
        model_path=str(onnx_yolu),
        confidence_threshold=conf,
        device=cihaz,
        load_at_init=True,
    )


# --- Tarama -------------------------------------------------------------------


def motoru_tara(model, goruntuler: list[Path], karo: int, ortusme: float,
                etiket: str) -> tuple[dict[Path, list[Kutu]], dict[str, float]]:
    """Bir motorla tum goruntuleri tarar; tahminleri ve sure olcumunu dondurur."""
    tahminler: dict[Path, list[Kutu]] = {}
    baslangic = time.perf_counter()
    for sira, yol in enumerate(goruntuler, start=1):
        tahminler[yol] = karolamali_tara(model, yol, karo, ortusme)
        if sira % 20 == 0 or sira == len(goruntuler):
            gecen = time.perf_counter() - baslangic
            print(f"  [{etiket}] {sira}/{len(goruntuler)} goruntu "
                  f"({gecen:.1f} sn)", flush=True)
    toplam = time.perf_counter() - baslangic
    return tahminler, {
        "toplam_sure": toplam,
        "goruntu_basina_sure": toplam / len(goruntuler) if goruntuler else 0.0,
    }


# --- Fark ve metrik satirlari -------------------------------------------------


def fark_satirlari(pt_tahmin: dict[Path, list[Kutu]], onnx_tahmin: dict[Path, list[Kutu]],
                   iou_esigi: float, goruntuler: list[Path]) -> list[dict]:
    """Her goruntude PyTorch ve ONNX tahminlerini eslestirip farklari yazar.

    Eslestirme projenin kendi ortak.kutulari_eslestir yardimciyla yapilir;
    yeni bir eslestirme yontemi yazilmaz."""
    satirlar: list[dict] = []
    for yol in goruntuler:
        pt = pt_tahmin.get(yol, [])
        onnx = onnx_tahmin.get(yol, [])
        eslesmeler, yalniz_pt, yalniz_onnx = kutulari_eslestir(pt, onnx, iou_esigi)

        for pt_idx, onnx_idx, iou in eslesmeler:
            a, b = pt[pt_idx], onnx[onnx_idx]
            satirlar.append({
                "goruntu": yol.name,
                "eslesme_durumu": "eslesti",
                "pytorch_x1": sayi_bicimle(a.x1), "pytorch_y1": sayi_bicimle(a.y1),
                "pytorch_x2": sayi_bicimle(a.x2), "pytorch_y2": sayi_bicimle(a.y2),
                "onnx_x1": sayi_bicimle(b.x1), "onnx_y1": sayi_bicimle(b.y1),
                "onnx_x2": sayi_bicimle(b.x2), "onnx_y2": sayi_bicimle(b.y2),
                "pytorch_skor": sayi_bicimle(a.skor, 6),
                "onnx_skor": sayi_bicimle(b.skor, 6),
                "kutu_iou": sayi_bicimle(iou, 6),
                "skor_mutlak_fark": sayi_bicimle(abs(a.skor - b.skor), 8),
                "x1_mutlak_fark": sayi_bicimle(abs(a.x1 - b.x1), 6),
                "y1_mutlak_fark": sayi_bicimle(abs(a.y1 - b.y1), 6),
                "x2_mutlak_fark": sayi_bicimle(abs(a.x2 - b.x2), 6),
                "y2_mutlak_fark": sayi_bicimle(abs(a.y2 - b.y2), 6),
            })
        for idx in yalniz_pt:
            a = pt[idx]
            satirlar.append({
                "goruntu": yol.name, "eslesme_durumu": "yalniz_pytorch",
                "pytorch_x1": sayi_bicimle(a.x1), "pytorch_y1": sayi_bicimle(a.y1),
                "pytorch_x2": sayi_bicimle(a.x2), "pytorch_y2": sayi_bicimle(a.y2),
                "onnx_x1": "", "onnx_y1": "", "onnx_x2": "", "onnx_y2": "",
                "pytorch_skor": sayi_bicimle(a.skor, 6), "onnx_skor": "",
                "kutu_iou": "", "skor_mutlak_fark": "",
                "x1_mutlak_fark": "", "y1_mutlak_fark": "",
                "x2_mutlak_fark": "", "y2_mutlak_fark": "",
            })
        for idx in yalniz_onnx:
            b = onnx[idx]
            satirlar.append({
                "goruntu": yol.name, "eslesme_durumu": "yalniz_onnx",
                "pytorch_x1": "", "pytorch_y1": "", "pytorch_x2": "", "pytorch_y2": "",
                "onnx_x1": sayi_bicimle(b.x1), "onnx_y1": sayi_bicimle(b.y1),
                "onnx_x2": sayi_bicimle(b.x2), "onnx_y2": sayi_bicimle(b.y2),
                "pytorch_skor": "", "onnx_skor": sayi_bicimle(b.skor, 6),
                "kutu_iou": "", "skor_mutlak_fark": "",
                "x1_mutlak_fark": "", "y1_mutlak_fark": "",
                "x2_mutlak_fark": "", "y2_mutlak_fark": "",
            })
    return satirlar


def metrik_satirlari(gercekler, tahminler: dict[str, dict], sureler: dict[str, dict],
                     esikler: list[float], iou_esigi: float) -> list[dict]:
    """Her esik icin iki motorun metrikleri ve aralarindaki farklar."""
    satirlar = []
    for conf in esikler:
        olculen = {
            motor: esikte_degerlendir(gercekler, tahminler[motor], conf, iou_esigi)
            for motor in MOTORLAR
        }
        tahmin_sayisi = {
            motor: sum(
                1 for kutular in tahminler[motor].values() for k in kutular if k.skor >= conf
            )
            for motor in MOTORLAR
        }
        satir = {"conf_esigi": conf, "goruntu_sayisi": len(gercekler),
                 "hedef_sayisi": int(olculen["pytorch"]["gercek_kutu"])}
        for motor in MOTORLAR:
            m = olculen[motor]
            satir.update({
                f"{motor}_tp": int(m["dogru_bulunan_tp"]),
                f"{motor}_fn": int(m["kacirilan_fn"]),
                f"{motor}_recall": sayi_bicimle(m["recall"]),
                f"{motor}_fp": int(m["yanlis_pozitif_fp"]),
                f"{motor}_fp_goruntu_basina": sayi_bicimle(m["fp_goruntu_basina"], 2),
                f"{motor}_precision": sayi_bicimle(m["precision"]),
                f"{motor}_toplam_tahmin": tahmin_sayisi[motor],
                f"{motor}_goruntu_basina_sure": sayi_bicimle(
                    sureler[motor]["goruntu_basina_sure"], 3),
                f"{motor}_toplam_sure": sayi_bicimle(sureler[motor]["toplam_sure"], 1),
            })
        p, o = olculen["pytorch"], olculen["onnx"]
        satir.update({
            "fark_tp": int(o["dogru_bulunan_tp"] - p["dogru_bulunan_tp"]),
            "fark_fn": int(o["kacirilan_fn"] - p["kacirilan_fn"]),
            "fark_recall": sayi_bicimle(o["recall"] - p["recall"]),
            "fark_fp": int(o["yanlis_pozitif_fp"] - p["yanlis_pozitif_fp"]),
            "fark_fp_goruntu_basina": sayi_bicimle(
                o["fp_goruntu_basina"] - p["fp_goruntu_basina"], 2),
            "fark_precision": sayi_bicimle(o["precision"] - p["precision"]),
        })
        satirlar.append(satir)
    return satirlar


ESLESME_ALANLARI = (
    ("dogru_bulunan_tp", "pytorch_tp", int),
    ("kacirilan_fn", "pytorch_fn", int),
    ("yanlis_pozitif_fp", "pytorch_fp", int),
    ("recall", "pytorch_recall", float),
    ("fp_goruntu_basina", "pytorch_fp_goruntu_basina", float),
    ("precision", "pytorch_precision", float),
    ("goruntu_sayisi", "goruntu_sayisi", int),
    ("gercek_kutu", "hedef_sayisi", int),
)


def capraz_kontrol(metrikler: list[dict], kayit: dict[float, dict]) -> list[dict]:
    """Yeni PyTorch kosusunu mevcut Model-512 olcumuyle karsilastirir."""
    satirlar = []
    for satir in metrikler:
        conf = satir["conf_esigi"]
        eski = kayit.get(conf)
        if eski is None:
            satirlar.append({"conf_esigi": conf, "alan": "(esik)", "mevcut_kayit": "yok",
                             "yeni_kosu": "", "sonuc": "UYUSMADI"})
            continue
        for eski_ad, yeni_ad, tur in ESLESME_ALANLARI:
            mevcut, yeni = tur(eski[eski_ad]), tur(satir[yeni_ad])
            satirlar.append({
                "conf_esigi": conf,
                "alan": yeni_ad,
                "mevcut_kayit": mevcut,
                "yeni_kosu": yeni,
                "sonuc": "UYUSTU" if mevcut == yeni else "UYUSMADI",
            })
    return satirlar


def motor_esitligi(metrikler: list[dict]) -> list[dict]:
    """PyTorch ve ONNX metriklerinin esik esik karsilastirmasi."""
    alanlar = ("tp", "fn", "fp", "recall", "fp_goruntu_basina", "precision")
    satirlar = []
    for satir in metrikler:
        for alan in alanlar:
            pt, onnx = satir[f"pytorch_{alan}"], satir[f"onnx_{alan}"]
            satirlar.append({
                "conf_esigi": satir["conf_esigi"], "alan": alan,
                "pytorch": pt, "onnx": onnx,
                "sonuc": "AYNI" if pt == onnx else "FARKLI",
            })
    return satirlar


def main() -> None:
    arg = argumanlari_coz()

    protokol = protokol_oku(arg.olcum)
    pt_yolu = PROJE_KOK / protokol["model"]
    onnx_yolu = pt_yolu.with_suffix(".onnx")
    hashler = kaynaklari_dogrula(pt_yolu, onnx_yolu, arg.onnx_bilgi)

    print(f"Protokol ({arg.olcum.name}): bolum {protokol['bolum']} | karo "
          f"{protokol['karo']} | ortusme {protokol['ortusme']} | IoU {protokol['iou']} | "
          f"cihaz {protokol['cihaz']} | esikler {protokol['esikler']}")
    print(f"PyTorch modeli: {pt_yolu.name} ({hashler['pt'][:16]}...)")
    print(f"ONNX modeli   : {onnx_yolu.name} ({hashler['onnx'][:16]}...)")
    print("Kaynak kimligi export kaydiyla UYUSTU.\n", flush=True)

    goruntu_dizin, etiket_dizin = bolum_yolu(protokol["bolum"], arg.veri)
    goruntuler = goruntuleri_listele(goruntu_dizin, arg.limit or None)
    gercekler = gercekleri_yukle(goruntuler, etiket_dizin)
    taban_conf = min(protokol["esikler"])
    print(f"{len(goruntuler)} goruntu, taban conf {taban_conf} "
          f"(yuksek esikler sonradan filtrelenir)\n", flush=True)

    tahminler, sureler = {}, {}
    print("[pytorch] SAHI + Ultralytics .pt", flush=True)
    pt_model = model_kur(str(pt_yolu), taban_conf, protokol["cihaz"])
    tahminler["pytorch"], sureler["pytorch"] = motoru_tara(
        pt_model, goruntuler, protokol["karo"], protokol["ortusme"], "pytorch"
    )

    print("\n[onnx] SAHI dilimleme + backend/core/onnx_detector.py", flush=True)
    onnx_model = onnx_sahi_modeli(onnx_yolu, taban_conf, protokol["cihaz"])
    tahminler["onnx"], sureler["onnx"] = motoru_tara(
        onnx_model, goruntuler, protokol["karo"], protokol["ortusme"], "onnx"
    )

    metrikler = metrik_satirlari(
        gercekler, tahminler, sureler, protokol["esikler"], protokol["iou"]
    )
    kontrol = capraz_kontrol(metrikler, olculen_metrikler(arg.olcum))
    print("\n=== CAPRAZ KONTROL (yeni PyTorch kosusu ile mevcut olcum) ===")
    tablo_bas([s for s in kontrol if s["sonuc"] == "UYUSMADI"] or
              [{"sonuc": "tum alanlar UYUSTU", "alan": f"{len(kontrol)} karsilastirma"}])

    if any(s["sonuc"] == "UYUSMADI" for s in kontrol):
        print("\nA KAPISI GECMEDI (Kontrol 1): yeni PyTorch kosusu mevcut olcumu "
              "yeniden uretmedi. CSV yazilmadi, ONNX sonucu yorumlanmadi.")
        sys.exit(1)

    esitlik = motor_esitligi(metrikler)
    farkli = [s for s in esitlik if s["sonuc"] == "FARKLI"]

    fark = fark_satirlari(tahminler["pytorch"], tahminler["onnx"], protokol["iou"], goruntuler)
    kosu = kosu_bilgisi(
        protokol_kaynagi=arg.olcum.as_posix(),
        bolum=protokol["bolum"],
        karo_boyutu=protokol["karo"],
        ortusme_orani=protokol["ortusme"],
        iou_esigi=protokol["iou"],
        cihaz=protokol["cihaz"],
        taban_conf=taban_conf,
        pt_sha256=hashler["pt"],
        onnx_sha256=hashler["onnx"],
        pytorch_yolu=f"{pt_yolu.as_posix()} (SAHI + Ultralytics)",
        onnx_yolu=f"{onnx_yolu.as_posix()} (backend/core/onnx_detector.py, onnxruntime)",
        motor_secimi=(
            "ONNX tarafinda Ultralytics sarmalayicisi degil backend'in onnxruntime "
            "dedektoru olculdu; Celery'de calisacak motor budur"
        ),
        karo_indeksi_notu=(
            "SAHI ObjectPrediction karo satir/sutun bilgisini tasimaz; fark CSV'si "
            "karolar arasi NMS sonrasi tam goruntu koordinatlarini icerir"
        ),
        eslestirme=(
            f"ortak.kutulari_eslestir, IoU {protokol['iou']} "
            "(protokolun gercek kutu eslestirmesiyle ayni esik)"
        ),
        surum_onnxruntime=__import__("onnxruntime").__version__,
    )
    fark_csv = csv_yaz(arg.fark_cikti, fark, kosu)
    metrik_csv = csv_yaz(arg.metrik_cikti, metrikler, kosu)

    print("\n=== METRIK KARSILASTIRMA ===")
    tablo_bas(metrikler, [
        "conf_esigi", "hedef_sayisi",
        "pytorch_tp", "onnx_tp", "fark_tp",
        "pytorch_fn", "onnx_fn", "fark_fn",
        "pytorch_fp", "onnx_fp", "fark_fp",
        "pytorch_recall", "onnx_recall", "fark_recall",
        "pytorch_fp_goruntu_basina", "onnx_fp_goruntu_basina",
        "pytorch_precision", "onnx_precision",
        "pytorch_toplam_sure", "onnx_toplam_sure",
    ])

    eslesen = [s for s in fark if s["eslesme_durumu"] == "eslesti"]
    yalniz_pt = [s for s in fark if s["eslesme_durumu"] == "yalniz_pytorch"]
    yalniz_onnx = [s for s in fark if s["eslesme_durumu"] == "yalniz_onnx"]
    en_buyuk_skor = max((s["skor_mutlak_fark"] for s in eslesen), default=0.0)
    en_buyuk_koord = max(
        (max(s[f"{ad}_mutlak_fark"] for ad in ("x1", "y1", "x2", "y2")) for s in eslesen),
        default=0.0,
    )
    print(f"\nEslesen tahmin: {len(eslesen)} | yalniz PyTorch: {len(yalniz_pt)} | "
          f"yalniz ONNX: {len(yalniz_onnx)}")
    print(f"En buyuk skor farki     : {en_buyuk_skor}")
    print(f"En buyuk koordinat farki: {en_buyuk_koord}")
    print(f"\nFark CSV  : {fark_csv}  ({len(fark)} satir)")
    print(f"Metrik CSV: {metrik_csv}  ({len(metrikler)} satir)")

    print("\n=== A KAPISI ===")
    print("Kontrol 1 (PyTorch yeniden uretimi): GECTI")
    if farkli:
        print("Kontrol 2 (operasyonel ONNX esligi): GECMEDI")
        tablo_bas(farkli)
        print("\nA KAPISI GECMEDI.")
        sys.exit(1)
    print("Kontrol 2 (operasyonel ONNX esligi): GECTI "
          f"({len(esitlik)} alan, tum esiklerde ayni)")
    print("\nA KAPISI GECTI. Ham skor ve koordinat farklari fark CSV'sinde korundu; "
          "olculen sey metrik esitligidir, bit duzeyinde ayniligi degildir.")


if __name__ == "__main__":
    main()
