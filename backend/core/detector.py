"""Dedektor arayuzu, sahte uygulama ve gercek dedektor secimi.

Hafta 2'de gercek model yoktu; boru hatti FakeDetector ile dogrulandi. Hafta
4'te gercek Model-512 ONNX dedektoru yalnizca buraya, get_detector()
fabrikasinin arkasina eklendi; tasks.py ve uclar degismedi.

Secim ACIK bir veriye dayanir: ModelVersion.framework. "onnx" olan kosu gercek
modelle calisir, "fake" olan sahte dedektorde kalir. Gercek model yuklenemezse
SESSIZCE sahte dedektore DUSULMEZ -- hata yukselir, kare mevcut durum
makinesine gore failed olur.
"""
import hashlib
import logging
import random
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ModelVersion.framework degerleri. Gercek dedektor yalnizca ONNX_CERCEVESI
# icin kurulur.
ONNX_CERCEVESI = "onnx"
SAHTE_CERCEVE = "fake"


class Detector(ABC):
    """Tum dedektorlerin ortak arayuzu."""

    @abstractmethod
    def detect(self, image_path, tile):
        """Tek bir karo icin kutu listesi doner.

        image_path: goruntunun disk yolu (str).
        tile: (satir, sutun, x1, y1, x2, y2) -- karo duzlemi.

        Donus: (x1, y1, x2, y2, skor) besliler listesi. Koordinatlar KARO
        duzlemindedir, global degil; global'e cevirmek cagiranin isidir.
        """
        raise NotImplementedError


class FakeDetector(Detector):
    """Rastgele kutu ureten sahte dedektor.

    Rastgelelik frame'in sha256'si ile karo indeksinden TOHUMLANIR: ayni kare
    her zaman ayni sonucu verir. Test edilebilirlik icin sart -- aksi halde
    "ayni gorevi iki kez calistirmak tespitleri ikiye katlamiyor" testi, kutular
    zaten farkli ciktigi icin hicbir sey kanitlamaz.
    """

    MIN_KUTU = 0
    MAX_KUTU = 3
    MIN_SKOR = 0.05
    MAX_SKOR = 0.95
    MIN_UYKU_MS = 10
    MAX_UYKU_MS = 30

    def __init__(self, frame_sha256):
        self.frame_sha256 = frame_sha256

    def _rng(self, tile):
        satir, sutun = tile[0], tile[1]
        tohum_metni = f"{self.frame_sha256}:{satir}:{sutun}"
        tohum = int.from_bytes(
            hashlib.sha256(tohum_metni.encode("utf-8")).digest()[:8], "big"
        )
        return random.Random(tohum)

    def detect(self, image_path, tile):
        rng = self._rng(tile)

        # Uyku suresi de ayni tohumdan: gercek modelin karo basina maliyetini
        # taklit eder ama kosudan kosuya degismez.
        uyku_ms = rng.uniform(self.MIN_UYKU_MS, self.MAX_UYKU_MS)
        time.sleep(uyku_ms / 1000.0)

        _, _, x1, y1, x2, y2 = tile
        karo_genislik = x2 - x1
        karo_yukseklik = y2 - y1

        kutular = []
        for _ in range(rng.randint(self.MIN_KUTU, self.MAX_KUTU)):
            # Kutu karo icinde kalsin: once sol-ust, sonra en fazla karonun
            # kalan kismi kadar genislik/yukseklik.
            kx1 = rng.randint(0, max(0, karo_genislik - 2))
            ky1 = rng.randint(0, max(0, karo_yukseklik - 2))
            kx2 = rng.randint(kx1 + 1, karo_genislik)
            ky2 = rng.randint(ky1 + 1, karo_yukseklik)
            skor = rng.uniform(self.MIN_SKOR, self.MAX_SKOR)
            kutular.append((kx1, ky1, kx2, ky2, skor))
        return kutular


def get_detector(model_version, frame_sha256):
    """Dedektor fabrikasi.

    framework == "onnx" ise gercek ONNX dedektoru, aksi halde FakeDetector.
    Gercek dedektor kurulamazsa hata YUKSELIR: sahte dedektore dusmek, model
    bozukken sistemin "calisiyor" gorunmesi demektir.
    """
    cerceve = getattr(model_version, "framework", SAHTE_CERCEVE)
    if cerceve != ONNX_CERCEVESI:
        return FakeDetector(frame_sha256=frame_sha256)

    from django.conf import settings

    from .onnx_detector import ModelYuklenemedi, paylasilan_dedektor

    model_yolu = settings.ONNX_MODEL_PATH
    if not model_yolu:
        raise ModelYuklenemedi(
            "ONNX_MODEL_PATH ayarlanmamis; gercek dedektor icin model yolu gerekli."
        )
    try:
        # Oturum surec basina paylasilir: her karo (hatta her kare) icin yeni
        # oturum acmak modeli diskten tekrar okumak demektir.
        return paylasilan_dedektor(model_yolu, settings.DETECTION_STORE_FLOOR)
    except ModelYuklenemedi:
        logger.exception("Gercek ONNX dedektoru yuklenemedi: %s", model_yolu)
        raise
