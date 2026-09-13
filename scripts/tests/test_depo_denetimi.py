"""depo_denetimi.py kapisinin testleri.

Bir kapi yalnizca GECTIGI zaman degil, GECIRMEDIGI zaman da dogru calismali:
asagidaki testler hem gercek bulgularin yakalandigini hem de bilincli fixture
degerlerinin yanlis alarm uretmedigini olcer.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

PROJE_KOK = Path(__file__).resolve().parents[2]
SCRIPT_DIZIN = PROJE_KOK / "scripts"
sys.path.insert(0, str(SCRIPT_DIZIN))

_spec = importlib.util.spec_from_file_location(
    "depo_denetimi", SCRIPT_DIZIN / "depo_denetimi.py"
)
denetim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(denetim)


class TestYasakYollar:
    @pytest.mark.parametrize("yol", [
        ".env",
        "backend/.env",
        "agirliklar/model512_best.onnx",
        "yolo11n.pt",
        "frontend/node_modules/react/index.js",
        "frontend/dist/index.html",
        "data/heridal/test/images/a.jpg",
        "kaggle.json",
        "gizli.pem",
        "backend/db.sqlite3",
        ".DS_Store",
    ])
    def test_yakalanir(self, yol):
        assert denetim.yasak_yollari_bul([yol]), yol

    @pytest.mark.parametrize("yol", [
        ".env.example",
        "reports/taban_cizgisi.csv",
        "rapor/bolum_01.md",
        "backend/core/models.py",
        "frontend/src/Uygulama.tsx",
    ])
    def test_mesru_dosya_gecer(self, yol):
        assert denetim.yasak_yollari_bul([yol]) == [], yol


class TestIcerik:
    def _yaz(self, tmp_path, monkeypatch, ad, icerik):
        (tmp_path / ad).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / ad).write_text(icerik, encoding="utf-8")
        monkeypatch.setattr(denetim, "PROJE_KOK", tmp_path)
        return denetim.icerik_denetle([ad])

    def test_jwt_yakalanir(self, tmp_path, monkeypatch):
        sahte = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"
        bulgular = self._yaz(tmp_path, monkeypatch, "kod.py", f"token = '{sahte}'\n")
        assert any("JWT" in b for b in bulgular)

    def test_ozel_anahtar_yakalanir(self, tmp_path, monkeypatch):
        bulgular = self._yaz(
            tmp_path, monkeypatch, "kod.py", "-----BEGIN RSA PRIVATE KEY-----\n"
        )
        assert any("ozel anahtar" in b for b in bulgular)

    def test_yerel_mutlak_yol_yakalanir(self, tmp_path, monkeypatch):
        bulgular = self._yaz(
            tmp_path, monkeypatch, "kod.py", 'YOL = "/Users/biri/Desktop/proje"\n'
        )
        assert any("yerel mutlak yol" in b for b in bulgular)

    def test_tmp_yolu_yanlis_alarm_vermez(self, tmp_path, monkeypatch):
        """/tmp ortamdan bagimsizdir; makineye ozel degildir."""
        bulgular = self._yaz(
            tmp_path, monkeypatch, "kod.py", 'GECICI = "/tmp/gozcu/cikti.csv"\n'
        )
        assert bulgular == []

    def test_konteyner_yolu_yanlis_alarm_vermez(self, tmp_path, monkeypatch):
        bulgular = self._yaz(
            tmp_path, monkeypatch, "kod.py", 'MODEL = "/models/model512_best.onnx"\n'
        )
        assert bulgular == []

    def test_fixture_parolasi_yanlis_alarm_vermez(self, tmp_path, monkeypatch):
        """Test kullanicisinin parolasi olmadan kimlik testi yazilamaz."""
        bulgular = self._yaz(
            tmp_path, monkeypatch, "tests/conftest.py",
            'User.objects.create_user(username="a", password="gizli-parola-123")\n',
        )
        assert bulgular == []

    def test_uygulama_kodundaki_gomulu_parola_yakalanir(self, tmp_path, monkeypatch):
        bulgular = self._yaz(
            tmp_path, monkeypatch, "backend/core/ayar.py",
            'DB_PASSWORD = "uretim-parolasi-12345"\n',
        )
        assert any("gomulu sir" in b for b in bulgular)


class TestBuyukDosya:
    def test_sinirin_ustundeki_dosya_yakalanir(self, tmp_path, monkeypatch):
        (tmp_path / "buyuk.bin").write_bytes(b"0" * 2048)
        monkeypatch.setattr(denetim, "PROJE_KOK", tmp_path)
        assert denetim.buyuk_dosyalari_bul(["buyuk.bin"], sinir=1024)

    def test_sinirin_altindaki_dosya_gecer(self, tmp_path, monkeypatch):
        (tmp_path / "kucuk.bin").write_bytes(b"0" * 512)
        monkeypatch.setattr(denetim, "PROJE_KOK", tmp_path)
        assert denetim.buyuk_dosyalari_bul(["kucuk.bin"], sinir=1024) == []


def test_gercek_depo_temiz():
    """Kapinin kendisi bu depoda gecmeli; aksi halde CI kirmizi baslardi."""
    dosyalar = denetim.izlenen_dosyalar()
    assert dosyalar, "git ls-files bos dondu"
    bulgular = (
        denetim.yasak_yollari_bul(dosyalar)
        + denetim.icerik_denetle(dosyalar)
        + denetim.buyuk_dosyalari_bul(dosyalar)
    )
    assert bulgular == [], bulgular
