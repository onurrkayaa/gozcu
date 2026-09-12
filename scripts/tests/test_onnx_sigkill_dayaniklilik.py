"""20_onnx_sigkill_dayaniklilik.py icindeki kapi kurallarinin ve kayit
okuyucularinin testleri.

Gercek SIGKILL BURADA GONDERILMEZ: konteyner oldurme ana scriptin isidir.
Testler, kapinin hangi durumlarda kapandigini sentetik olcumlerle dogrular.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJE_KOK = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIZIN = PROJE_KOK / "scripts"
sys.path.insert(0, str(SCRIPT_DIZIN))

_spec = importlib.util.spec_from_file_location(
    "sigkill", SCRIPT_DIZIN / "20_onnx_sigkill_dayaniklilik.py"
)
sigkill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sigkill)


def saglikli_olcum(**degisiklik) -> dict:
    """Butun kontrollerin gectigi bir olcum; testler bunu bozarak calisir."""
    olcum = {
        "sigkill_dogrulandi": True,
        "sigkill_kaniti": "cikis kodu 137, konteyner durmus",
        "yeniden_teslim": "evet",
        "yeniden_teslim_suresi": 905.0,
        "toplam_frame": 4,
        "done_frame": 4,
        "failed_frame": 0,
        "takili_frame": 0,
        "kayip_frame": 0,
        "yinelenen_tespit": 0,
        "toplam_detection": 37,
        "toplam_detection_db": 37,
        "model_cercevesi": "onnx",
        "model_sha256": "abc123",
        "model_sha256_kayit": "abc123",
        "kosu_durumu": "done",
        "oldurulen_kare_son_durumu": "done",
    }
    olcum.update(degisiklik)
    return olcum


def kontrol_sonucu(olcum: dict, parca: str) -> str:
    for satir in sigkill.kapi_kontrolleri(olcum):
        if satir["kontrol"].startswith(parca):
            return satir["sonuc"]
    raise AssertionError(f"kontrol bulunamadi: {parca}")


# --- Saglikli durum -----------------------------------------------------------


def test_saglikli_kosuda_butun_kontroller_geciyor():
    """SIGKILL dogrulanmis, yeniden teslim olmus, kare kaybi yoksa kapi acik."""
    assert all(s["sonuc"] == "GECTI" for s in sigkill.kapi_kontrolleri(saglikli_olcum()))


# --- SIGKILL dogrulamasi ------------------------------------------------------


def test_graceful_stop_sigkill_sayilmiyor():
    """Konteyner duzgun kapanmissa (0 ile cikis) kapi gecmemeli."""
    olcum = saglikli_olcum(
        sigkill_dogrulandi=False, sigkill_kaniti="cikis kodu 0, duzgun kapanma"
    )
    assert kontrol_sonucu(olcum, "isci gercekten SIGKILL") == "GECMEDI"


def test_sigkill_cikis_kodu_sabiti_137():
    """SIGKILL kaniti 128+9 cikis koduna dayanir."""
    assert sigkill.SIGKILL_CIKIS_KODU == 137


# --- Yeniden teslim ve kare kaybi ---------------------------------------------


def test_yeniden_teslim_gorulmeden_kapi_gecmiyor():
    olcum = saglikli_olcum(yeniden_teslim="hayir", yeniden_teslim_suresi="olculmedi")
    assert kontrol_sonucu(olcum, "gorev yeniden teslim") == "GECMEDI"


def test_oldurulen_kare_bitmeden_kapi_gecmiyor():
    """Baska kareler bitse de OLDURULEN kare processing kaldiysa kapi gecmez."""
    olcum = saglikli_olcum(oldurulen_kare_son_durumu="processing")
    assert kontrol_sonucu(olcum, "oldurulen karenin son durumu") == "GECMEDI"


def test_takili_kare_kapiyi_kapatiyor():
    """processing/queued/pending kalan kare varsa kapi gecmez."""
    olcum = saglikli_olcum(done_frame=3, takili_frame=1)
    assert kontrol_sonucu(olcum, "takili kare") == "GECMEDI"
    assert kontrol_sonucu(olcum, "butun kareler son duruma") == "GECMEDI"


def test_kayip_kare_kapiyi_kapatiyor():
    olcum = saglikli_olcum(done_frame=3, kayip_frame=1)
    assert kontrol_sonucu(olcum, "kayip kare") == "GECMEDI"


def test_yinelenen_tespit_kapiyi_kapatiyor():
    """Idempotanslik bozulup ayni tespit iki kez yazilirsa kapi gecmez."""
    assert kontrol_sonucu(saglikli_olcum(yinelenen_tespit=12), "kontrolsuz yinelenen") == "GECMEDI"


def test_csv_ve_veritabani_toplami_uyusmazsa_kapi_gecmiyor():
    olcum = saglikli_olcum(toplam_detection=37, toplam_detection_db=40)
    assert kontrol_sonucu(olcum, "CSV tespit toplami") == "GECMEDI"


def test_sahte_dedektor_kapiyi_kapatiyor():
    assert kontrol_sonucu(saglikli_olcum(model_cercevesi="fake"), "gercek ONNX") == "GECMEDI"


def test_model_hashi_uyusmazsa_kapi_gecmiyor():
    olcum = saglikli_olcum(model_sha256="aaa", model_sha256_kayit="bbb")
    assert kontrol_sonucu(olcum, "model sha256") == "GECMEDI"


def test_kosu_son_duruma_ulasmadiysa_kapi_gecmiyor():
    assert kontrol_sonucu(saglikli_olcum(kosu_durumu="running"), "kosu son duruma") == "GECMEDI"


# --- Kayit okuyuculari --------------------------------------------------------


def test_tekrar_islenen_kareler_zamanlama_kaydindan_cikariliyor(tmp_path):
    """Ayni kare icin birden fazla satir varsa o kare tekrar islenmistir."""
    yol = tmp_path / "zamanlama.jsonl"
    satirlar = [
        {"run_id": 7, "frame_id": 1, "durum": "done"},
        {"run_id": 7, "frame_id": 2, "durum": "done"},
        {"run_id": 7, "frame_id": 2, "durum": "done"},   # yeniden teslim
        {"run_id": 9, "frame_id": 3, "durum": "done"},   # baska kosu
    ]
    yol.write_text("\n".join(json.dumps(s) for s in satirlar) + "\n", encoding="utf-8")

    assert sigkill.tekrar_islenen_kareler(yol, 7) == {2: 2}
    assert sigkill.tekrar_islenen_kareler(yol, 9) == {}
    assert sigkill.tekrar_islenen_kareler(tmp_path / "yok.jsonl", 7) == {}


def test_konteyner_durumu_docker_ciktisini_cozuyor(monkeypatch):
    """docker inspect ciktisi calisma durumu, cikis kodu ve yeniden baslamaya ayrilir."""
    monkeypatch.setattr(
        sigkill, "komut", lambda *a, **k: "false|137|2|2026-09-12T10:00:00Z\n"
    )
    durum = sigkill.konteyner_durumu("gozcu_worker")
    assert durum["calisiyor"] is False
    assert durum["cikis_kodu"] == 137
    assert durum["yeniden_baslama"] == 2

    monkeypatch.setattr(sigkill, "komut", lambda *a, **k: "")
    yok = sigkill.konteyner_durumu("olmayan")
    assert yok["calisiyor"] is False and yok["cikis_kodu"] is None


def test_son_ve_takili_durum_kumeleri_ayrik():
    """Son durumlar ile takili durumlar kesismemeli."""
    assert not set(sigkill.SON_DURUMLAR) & set(sigkill.TAKILI_DURUMLAR)
    assert set(sigkill.TAKILI_DURUMLAR) == {"pending", "queued", "processing"}
