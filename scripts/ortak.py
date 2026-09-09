"""Tum scriptlerin paylastigi yardimci fonksiyonlar: yol cozme, etiket okuma,
IoU hesabi, tahmin-gercek eslestirme, metrik hesabi ve kosu bilgisi uretimi."""

from __future__ import annotations

import csv
import platform
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# --- Sabit yollar. Kodun icine gomulu tek yol tanimi burasi; scriptler
# --- --veri argumaniyla bunu gecersiz kilabilir.
PROJE_KOK = Path(__file__).resolve().parent.parent
VERI_KOK = PROJE_KOK / "data" / "heridal"
RAPOR_KOK = PROJE_KOK / "reports"

# Veri kumesindeki tek sinifin adi 'human'; COCO ile egitilmis modelde karsiligi
# 'person' (sinif kimligi 0). Ikisi ayni seyi kastediyor.
COCO_PERSON_ID = 0
GECERLI_UZANTILAR = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True)
class Kutu:
    """Piksel cinsinden bir sinirlayici kutu; skor sadece tahminlerde doludur."""

    x1: float
    y1: float
    x2: float
    y2: float
    skor: float = 1.0

    @property
    def genislik(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def yukseklik(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def alan(self) -> float:
        return self.genislik * self.yukseklik


def bolum_yolu(bolum: str, veri_kok: Path = VERI_KOK) -> tuple[Path, Path]:
    """Verilen bolum adi icin (images, labels) klasor ciftini dondurur ve varligini dogrular."""
    goruntu_dizin = veri_kok / bolum / "images"
    etiket_dizin = veri_kok / bolum / "labels"
    if not goruntu_dizin.is_dir():
        raise FileNotFoundError(f"Goruntu klasoru bulunamadi: {goruntu_dizin}")
    if not etiket_dizin.is_dir():
        raise FileNotFoundError(f"Etiket klasoru bulunamadi: {etiket_dizin}")
    return goruntu_dizin, etiket_dizin


def goruntuleri_listele(goruntu_dizin: Path, limit: int | None = None) -> list[Path]:
    """Klasordeki goruntuleri ada gore siralayip dondurur; siralama tekrar
    calistirmalarda ayni sonucu garanti eder."""
    dosyalar = sorted(
        p for p in goruntu_dizin.iterdir()
        if p.is_file() and p.suffix.lower() in GECERLI_UZANTILAR
    )
    if limit is not None and limit > 0:
        dosyalar = dosyalar[:limit]
    return dosyalar


def etiket_yolu(goruntu: Path, etiket_dizin: Path) -> Path:
    """Bir goruntu dosyasina karsilik gelen YOLO .txt etiket yolunu uretir."""
    return etiket_dizin / (goruntu.stem + ".txt")


def yolo_etiket_oku(etiket_dosya: Path, genislik: int, yukseklik: int) -> list[Kutu]:
    """YOLO formatindaki (sinif, xmerkez, ymerkez, w, h; hepsi 0-1) etiketleri
    piksel kosesi kutularina cevirir; dosya yoksa bos liste doner."""
    if not etiket_dosya.is_file():
        return []
    kutular: list[Kutu] = []
    for satir in etiket_dosya.read_text(encoding="utf-8").splitlines():
        parcalar = satir.split()
        # YOLO satiri en az 5 alan icerir; segmentasyon satirlarini (daha uzun) atlariz.
        if len(parcalar) < 5:
            continue
        _, xm, ym, w, h = (float(p) for p in parcalar[:5])
        kutular.append(
            Kutu(
                x1=(xm - w / 2) * genislik,
                y1=(ym - h / 2) * yukseklik,
                x2=(xm + w / 2) * genislik,
                y2=(ym + h / 2) * yukseklik,
            )
        )
    return kutular


def iou_hesapla(a: Kutu, b: Kutu) -> float:
    """Iki kutunun kesisim/birlesim oranini (IoU) dondurur; kesisim yoksa 0.0."""
    kesisim_x1 = max(a.x1, b.x1)
    kesisim_y1 = max(a.y1, b.y1)
    kesisim_x2 = min(a.x2, b.x2)
    kesisim_y2 = min(a.y2, b.y2)

    kesisim_g = max(0.0, kesisim_x2 - kesisim_x1)
    kesisim_y = max(0.0, kesisim_y2 - kesisim_y1)
    kesisim = kesisim_g * kesisim_y
    if kesisim <= 0.0:
        return 0.0

    birlesim = a.alan + b.alan - kesisim
    if birlesim <= 0.0:
        return 0.0
    return kesisim / birlesim


def kutulari_eslestir(
    gercekler: list[Kutu],
    tahminler: list[Kutu],
    iou_esigi: float = 0.3,
) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    """Tahminleri guven skoruna gore azalan sirada gezerek her gercek kutuyu en
    fazla bir tahminle eslestirir; (eslesmeler, eslesmeyen_gercekler,
    eslesmeyen_tahminler) dondurur."""
    # Yuksek skorlu tahmin oncelikli. Skor esitliginde indeks sirasi belirleyici
    # olsun ki ayni girdi her calistirmada ayni sonucu versin.
    sirali_tahmin = sorted(
        range(len(tahminler)), key=lambda i: (-tahminler[i].skor, i)
    )

    kullanilmis_gercek: set[int] = set()
    eslesmeler: list[tuple[int, int, float]] = []
    eslesmeyen_tahmin: list[int] = []

    for t_idx in sirali_tahmin:
        en_iyi_g = -1
        en_iyi_iou = 0.0
        for g_idx, gercek in enumerate(gercekler):
            if g_idx in kullanilmis_gercek:
                continue
            deger = iou_hesapla(gercek, tahminler[t_idx])
            if deger >= iou_esigi and deger > en_iyi_iou:
                en_iyi_iou = deger
                en_iyi_g = g_idx
        if en_iyi_g >= 0:
            kullanilmis_gercek.add(en_iyi_g)
            eslesmeler.append((en_iyi_g, t_idx, en_iyi_iou))
        else:
            eslesmeyen_tahmin.append(t_idx)

    eslesmeyen_gercek = [i for i in range(len(gercekler)) if i not in kullanilmis_gercek]
    return eslesmeler, eslesmeyen_gercek, sorted(eslesmeyen_tahmin)


def metrik_hesapla(tp: int, fn: int, fp: int, goruntu_sayisi: int) -> dict[str, float]:
    """TP/FN/FP sayimlarindan recall, precision ve goruntu basina FP degerlerini uretir."""
    gercek_toplam = tp + fn
    return {
        "gercek_kutu": gercek_toplam,
        "dogru_bulunan_tp": tp,
        "kacirilan_fn": fn,
        "recall": tp / gercek_toplam if gercek_toplam else 0.0,
        "yanlis_pozitif_fp": fp,
        "fp_goruntu_basina": fp / goruntu_sayisi if goruntu_sayisi else 0.0,
        "precision": tp / (tp + fp) if (tp + fp) else 0.0,
    }


def surum_bilgisi() -> dict[str, str]:
    """Kosuyu tekrar uretilebilir kilmak icin python ve ana paket surumlerini toplar."""
    surumler = {"python": platform.python_version()}
    for paket in ("ultralytics", "sahi", "torch"):
        try:
            modul = __import__(paket)
            surumler[paket] = getattr(modul, "__version__", "bilinmiyor")
        except Exception:
            surumler[paket] = "kurulu-degil"
    return surumler


def kosu_bilgisi(**alanlar) -> dict[str, str]:
    """CSV'ye gomulecek kosu bilgisini (parametreler + surumler + tarih) tek sozlukte toplar."""
    bilgi = {f"kosu_{ad}": str(deger) for ad, deger in alanlar.items()}
    for ad, deger in surum_bilgisi().items():
        bilgi[f"kosu_surum_{ad}"] = deger
    bilgi["kosu_tarih"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    bilgi["kosu_komut"] = " ".join(sys.argv)
    return bilgi


def csv_yaz(hedef: Path, satirlar: list[dict], kosu: dict[str, str] | None = None) -> Path:
    """Satirlari CSV'ye yazar; kosu bilgisi verilmisse her satira sabit sutun olarak ekler."""
    if not satirlar:
        raise ValueError("Yazilacak satir yok")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    zenginlestirilmis = [{**satir, **(kosu or {})} for satir in satirlar]
    basliklar = list(zenginlestirilmis[0].keys())
    with hedef.open("w", newline="", encoding="utf-8") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=basliklar)
        yazici.writeheader()
        yazici.writerows(zenginlestirilmis)
    return hedef


def tablo_bas(satirlar: list[dict], sutunlar: list[str] | None = None) -> None:
    """Satirlari terminale hizalanmis, okunabilir bir tablo olarak basar."""
    if not satirlar:
        print("(satir yok)")
        return
    sutunlar = sutunlar or list(satirlar[0].keys())
    metin = [[f"{s.get(c, '')}" for c in sutunlar] for s in satirlar]
    genislik = [
        max(len(sutunlar[i]), max(len(satir[i]) for satir in metin))
        for i in range(len(sutunlar))
    ]
    ayirac = "-+-".join("-" * g for g in genislik)
    print(" | ".join(b.ljust(genislik[i]) for i, b in enumerate(sutunlar)))
    print(ayirac)
    for satir in metin:
        print(" | ".join(h.ljust(genislik[i]) for i, h in enumerate(satir)))


def sayi_bicimle(deger: float, basamak: int = 4) -> float:
    """Kayan noktali degeri CSV ve ekran icin sabit basamaga yuvarlar."""
    return round(float(deger), basamak)


# --- Model tarama katmani -----------------------------------------------------
# Asagidaki sabitler 01, 02 ve 03 scriptlerinin AYNI tarama rejimini kullanmasini
# garanti eder. Degistirilirse uc scriptin sonucu birlikte degisir.

# SAHI varsayilan olarak karolara EK OLARAK tum goruntuyu de kucultup tarar
# (perform_standard_pred=True). Acik birakilirsa "karolamali" olcum, karolamasiz
# olcumu zaten icinde barindirir ve karolamanin tek basina katkisi olculemez.
PERFORM_STANDARD_PRED = False

# SAHI, guven esigi dusukken kutu birlestirmeyi (GREEDYNMM/IOS) kendiliginden
# NMS/IOU'ya cevirir. Sabitlemezsek ayni goruntu farkli conf degerlerinde farkli
# birlestirme rejiminde islenir; bu da "tek tarama + sonradan filtreleme"
# optimizasyonunu bozar ve sonuclari tekrarlanamaz kilar.
POSTPROCESS_TYPE = "NMS"
POSTPROCESS_MATCH_METRIC = "IOU"

# Karolamasiz modda modelin kendi icinde kuculttugu giris boyutu.
KAROLAMASIZ_GIRIS = 640


def model_kur(model_yolu: str, conf_esigi: float, cihaz: str = "cpu"):
    """SAHI AutoDetectionModel nesnesini kurar; conf esigi tarama sirasinda
    uygulanan alt sinirdir."""
    from sahi import AutoDetectionModel

    return AutoDetectionModel.from_pretrained(
        model_type="ultralytics",
        model_path=model_yolu,
        confidence_threshold=conf_esigi,
        device=cihaz,
    )


def tahminleri_kutuya_cevir(sahi_sonuc) -> list[Kutu]:
    """SAHI tahminlerini sadece person sinifiyla sinirlayip Kutu listesine cevirir."""
    kutular: list[Kutu] = []
    for tahmin in sahi_sonuc.object_prediction_list:
        # COCO'da person sinif kimligi 0; diger tum siniflari atiyoruz.
        if tahmin.category.id != COCO_PERSON_ID:
            continue
        x1, y1, x2, y2 = tahmin.bbox.to_xyxy()
        kutular.append(Kutu(x1, y1, x2, y2, skor=float(tahmin.score.value)))
    return kutular


def karolamali_tara(model, goruntu_yolu: Path, karo: int, ortusme: float) -> list[Kutu]:
    """Goruntuyu SAHI ile karolara bolerek tarar ve person tahminlerini dondurur."""
    from sahi.predict import get_sliced_prediction

    sonuc = get_sliced_prediction(
        str(goruntu_yolu),
        model,
        slice_height=karo,
        slice_width=karo,
        overlap_height_ratio=ortusme,
        overlap_width_ratio=ortusme,
        perform_standard_pred=PERFORM_STANDARD_PRED,
        postprocess_type=POSTPROCESS_TYPE,
        postprocess_match_metric=POSTPROCESS_MATCH_METRIC,
        postprocess_class_agnostic=False,
        verbose=0,
    )
    return tahminleri_kutuya_cevir(sonuc)


def karolamasiz_tara(model, goruntu_yolu: Path) -> list[Kutu]:
    """Tum goruntuyu tek parca halinde modele verir; model onu kendi giris boyutuna
    (640) kucultur. Karolamanin katkisini olcmek icin karsilastirma tarafidir."""
    from sahi.predict import get_prediction

    sonuc = get_prediction(str(goruntu_yolu), model)
    return tahminleri_kutuya_cevir(sonuc)


def gercekleri_yukle(goruntuler: list[Path], etiket_dizin: Path) -> dict[Path, list[Kutu]]:
    """Her goruntu icin YOLO etiketlerini piksel kutulari olarak okur."""
    from PIL import Image

    gercekler: dict[Path, list[Kutu]] = {}
    for yol in goruntuler:
        with Image.open(yol) as gorsel:
            genislik, yukseklik = gorsel.size
        gercekler[yol] = yolo_etiket_oku(etiket_yolu(yol, etiket_dizin), genislik, yukseklik)
    return gercekler


def esikte_degerlendir(
    gercekler: dict[Path, list[Kutu]],
    tahminler: dict[Path, list[Kutu]],
    conf: float,
    iou_esigi: float,
) -> dict[str, float]:
    """Verilen guven esigi icin tahminleri filtreleyip tum goruntuler uzerinde
    TP/FN/FP toplar ve metrikleri dondurur."""
    tp = fn = fp = 0
    for yol, gercek_kutular in gercekler.items():
        secilen = [k for k in tahminler.get(yol, []) if k.skor >= conf]
        eslesmeler, eslesmeyen_gercek, eslesmeyen_tahmin = kutulari_eslestir(
            gercek_kutular, secilen, iou_esigi
        )
        tp += len(eslesmeler)
        fn += len(eslesmeyen_gercek)
        fp += len(eslesmeyen_tahmin)
    return metrik_hesapla(tp, fn, fp, len(gercekler))
