"""Gercek Model-512 dedektoru: ONNX Runtime ile karo bazinda cikarim.

TEK ONNX YOLU. Bu modul hem olcum scriptinin (scripts/18) ONNX tarafinda hem de
Celery gorevinde kullanilir; boylece "olculen motor" ile "uretimde calisan motor"
ayni koddur. Torch veya ultralytics gerektirmez: yalnizca onnxruntime, numpy ve
Pillow.

Karolama BURADA YENIDEN YAZILMAZ: Celery yolu core.tiling.karolari_hesapla ile
uretilen karolari alir, olcum yolu SAHI'nin dilimlerini verir. Karo icindeki
NMS de core.tiling.nms'tir.

Son islem, Ultralytics'in kendi cikarim yolunun yaptigi islemlerin aynisidir:
    - girdi RGB, 0-1 araligina bolunmus, CHW duzeninde float32
    - karo giris boyutundan kucukse mektup kutusu (letterbox) ile ortalanip
      114 ile doldurulur, kutular sonra geri olceklenir
    - cikti (1, 4+sinif, aday) -> aday basina (cx, cy, w, h, skor)
    - guven esigi KESIN buyuktur ile uygulanir (Ultralytics: conf > esik)
    - karo ici NMS: IoU esigi ASILIRSA bastir, en fazla max_det kutu
"""
from __future__ import annotations

import ast
import threading
import time
from pathlib import Path

from .detector import Detector
from .tiling import nms

# Ultralytics cikarim varsayilanlari. Olcum ve uretim ayni degerleri kullanmak
# ZORUNDA; degistirilirse iki taraf birbirinden kayar.
KARO_ICI_NMS_IOU = 0.7
MAKS_TESPIT = 300
DOLGU_DEGERI = 114

# Model metadata'sinda beklenen sinif. Baska bir sinif kumesi gelirse tespitler
# sessizce yanlis etiketlenir; bu yuzden yukleme sirasinda dogrulanir.
BEKLENEN_SINIFLAR = {0: "human"}


class ModelYuklenemedi(RuntimeError):
    """ONNX modeli acilamadi veya beklenen kimlikte degil."""


def _mektup_kutusu(karo_rgb, hedef_boy: int):
    """Karoyu hedef kareye olcekler ve ortalayarak doldurur.

    (tensor_girdisi, olcek, (dolgu_x, dolgu_y)) dondurur. Karo zaten hedef
    boyuttaysa olcekleme ve dolgu yapilmaz (olcum protokolundeki durum budur)."""
    import numpy as np
    from PIL import Image

    yukseklik, genislik = karo_rgb.shape[:2]
    if (yukseklik, genislik) == (hedef_boy, hedef_boy):
        return karo_rgb, 1.0, (0.0, 0.0)

    olcek = min(hedef_boy / yukseklik, hedef_boy / genislik)
    yeni_g, yeni_y = round(genislik * olcek), round(yukseklik * olcek)
    dolgu_x = (hedef_boy - yeni_g) / 2
    dolgu_y = (hedef_boy - yeni_y) / 2

    kucuk = Image.fromarray(karo_rgb).resize((yeni_g, yeni_y), Image.BILINEAR)
    tuval = np.full((hedef_boy, hedef_boy, 3), DOLGU_DEGERI, dtype=np.uint8)
    ust, sol = int(round(dolgu_y - 0.1)), int(round(dolgu_x - 0.1))
    tuval[ust:ust + yeni_y, sol:sol + yeni_g] = np.asarray(kucuk)
    return tuval, olcek, (dolgu_x, dolgu_y)


class OnnxDedektor(Detector):
    """ONNX Runtime oturumunu bir kez acar ve her karo icin yeniden kullanir."""

    def __init__(self, model_yolu, conf_esigi, giris_boyu=None,
                 saglayicilar=("CPUExecutionProvider",)):
        import onnxruntime as ort

        self.model_yolu = Path(model_yolu)
        if not self.model_yolu.is_file():
            raise ModelYuklenemedi(f"ONNX modeli bulunamadi: {self.model_yolu}")

        self.conf_esigi = float(conf_esigi)
        baslangic = time.perf_counter()
        try:
            self.oturum = ort.InferenceSession(
                str(self.model_yolu), providers=list(saglayicilar)
            )
        except Exception as hata:  # noqa: BLE001 - sebep disari aynen tasinir
            raise ModelYuklenemedi(
                f"ONNX oturumu acilamadi ({self.model_yolu}): {hata}"
            ) from hata
        # Oturumun ilk kurulumu (soguk baslangic) ayri tutulur: ilk karenin
        # suresi bu yuzden digerlerinden buyuktur ve ortalamaya sessizce
        # karistirilmamalidir.
        self.kurulum_suresi = time.perf_counter() - baslangic
        self.kare_sayisi = 0
        self.sayaclar = {"goruntu_okuma": 0.0, "cikarim": 0.0, "son_islem": 0.0}

        girdi = self.oturum.get_inputs()[0]
        self.girdi_adi = girdi.name
        self.girdi_sekli = girdi.shape
        self.cikti_adlari = [c.name for c in self.oturum.get_outputs()]

        metadata = self.oturum.get_modelmeta().custom_metadata_map
        self.sinif_adlari = self._siniflari_coz(metadata)
        if self.sinif_adlari != BEKLENEN_SINIFLAR:
            raise ModelYuklenemedi(
                f"Model sinif kumesi beklenenden farkli: {self.sinif_adlari} "
                f"(beklenen {BEKLENEN_SINIFLAR})"
            )
        self.giris_boyu = giris_boyu or self._giris_boyunu_coz(metadata, self.girdi_sekli)

    @staticmethod
    def _siniflari_coz(metadata) -> dict:
        ham = metadata.get("names")
        if not ham:
            raise ModelYuklenemedi("Model metadata'sinda sinif adlari yok")
        return {int(k): str(v) for k, v in ast.literal_eval(ham).items()}

    @staticmethod
    def _giris_boyunu_coz(metadata, girdi_sekli) -> int:
        # Once grafigin kendi sabit sekli; dinamikse metadata'daki imgsz.
        if isinstance(girdi_sekli[2], int) and isinstance(girdi_sekli[3], int):
            if girdi_sekli[2] != girdi_sekli[3]:
                raise ModelYuklenemedi(f"Kare olmayan giris sekli: {girdi_sekli}")
            return int(girdi_sekli[2])
        imgsz = metadata.get("imgsz")
        if not imgsz:
            raise ModelYuklenemedi("Giris boyu ne grafikten ne metadata'dan okunabildi")
        return int(ast.literal_eval(imgsz)[0])

    # --- Cikarim -------------------------------------------------------------

    def karo_tahmin_et(self, karo_rgb):
        """Tek bir karo goruntusu (RGB, HWC, uint8) icin kutu listesi.

        Donus: karo duzleminde (x1, y1, x2, y2, skor) besliler, skora gore
        azalan sirada."""
        import numpy as np

        yukseklik, genislik = karo_rgb.shape[:2]
        tuval, olcek, (dolgu_x, dolgu_y) = _mektup_kutusu(karo_rgb, self.giris_boyu)

        tensor = np.ascontiguousarray(
            tuval.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        )
        cikarim_basi = time.perf_counter()
        ham = self.oturum.run(self.cikti_adlari, {self.girdi_adi: tensor})[0]
        self.sayaclar["cikarim"] += time.perf_counter() - cikarim_basi
        son_islem_basi = time.perf_counter()

        # (1, 4 + sinif, aday) -> (aday, 4 + sinif)
        adaylar = ham[0].T
        skorlar = adaylar[:, 4:].max(axis=1)
        secilen = adaylar[skorlar > self.conf_esigi]
        skorlar = skorlar[skorlar > self.conf_esigi]
        if len(secilen) == 0:
            self.sayaclar["son_islem"] += time.perf_counter() - son_islem_basi
            return []

        cx, cy, g, y = secilen[:, 0], secilen[:, 1], secilen[:, 2], secilen[:, 3]
        kutular = [
            (
                float(cx[i] - g[i] / 2), float(cy[i] - y[i] / 2),
                float(cx[i] + g[i] / 2), float(cy[i] + y[i] / 2),
                float(skorlar[i]),
            )
            for i in range(len(secilen))
        ]
        # Karo ici NMS: core.tiling.nms ile, ikinci bir uygulama yazilmadan.
        tutulan = nms(kutular, KARO_ICI_NMS_IOU)[:MAKS_TESPIT]

        sonuc = []
        for x1, y1, x2, y2, skor in tutulan:
            # Mektup kutusu dolgusunu cikar, olcegi geri al, karo sinirina kirp.
            x1 = min(max((x1 - dolgu_x) / olcek, 0.0), genislik)
            y1 = min(max((y1 - dolgu_y) / olcek, 0.0), yukseklik)
            x2 = min(max((x2 - dolgu_x) / olcek, 0.0), genislik)
            y2 = min(max((y2 - dolgu_y) / olcek, 0.0), yukseklik)
            if x2 <= x1 or y2 <= y1:
                continue
            sonuc.append((x1, y1, x2, y2, skor))
        self.sayaclar["son_islem"] += time.perf_counter() - son_islem_basi
        return sonuc

    def olcum_sifirla(self):
        """Yeni bir kareye baslarken asama sayaclarini sifirlar ve kare sayar."""
        self.kare_sayisi += 1
        self.sayaclar = {ad: 0.0 for ad in self.sayaclar}

    def olcum_al(self) -> dict:
        """Bu karede biriken asama surelerinin kopyasi."""
        return dict(self.sayaclar)

    def detect(self, image_path, tile):
        """Detector arayuzu: karoyu goruntuden kesip tahmin eder."""
        import numpy as np
        from PIL import Image

        _, _, x1, y1, x2, y2 = tile
        okuma_basi = time.perf_counter()
        with Image.open(image_path) as gorsel:
            karo = np.asarray(gorsel.convert("RGB").crop((x1, y1, x2, y2)))
        self.sayaclar["goruntu_okuma"] += time.perf_counter() - okuma_basi
        return self.karo_tahmin_et(karo)


# --- Surec basina paylasilan oturum ------------------------------------------
# ONNX Runtime oturumunu her karo (hatta her kare) icin yeniden acmak modeli
# diskten tekrar okumak demektir. Isci sureci icinde model yolu + esik basina
# tek ornek tutulur; Celery iscisi surec basina havuzladigi icin bu yeterli.

_ORNEKLER: dict = {}
_KILIT = threading.Lock()


def paylasilan_dedektor(model_yolu, conf_esigi, **kwargs) -> OnnxDedektor:
    """Ayni model yolu ve esik icin surec basina tek OnnxDedektor dondurur."""
    anahtar = (str(model_yolu), float(conf_esigi))
    ornek = _ORNEKLER.get(anahtar)
    if ornek is not None:
        return ornek
    with _KILIT:
        ornek = _ORNEKLER.get(anahtar)
        if ornek is None:
            ornek = OnnxDedektor(model_yolu, conf_esigi, **kwargs)
            _ORNEKLER[anahtar] = ornek
    return ornek
