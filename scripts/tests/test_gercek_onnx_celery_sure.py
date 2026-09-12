"""19_gercek_onnx_celery_sure.py icindeki ozet, kapi ve zaman asimi kararinin
testleri.

Gercek Celery kosusu BURADA TEKRARLANMAZ: 157 karelik kosu ana scriptin isidir.
Testler saf islevleri (yuzdelik, ozet, kapi kurallari, karar kurali) sentetik
kayitlarla olcer.
"""

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

PROJE_KOK = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIZIN = PROJE_KOK / "scripts"
sys.path.insert(0, str(SCRIPT_DIZIN))

_spec = importlib.util.spec_from_file_location(
    "celery_sure", SCRIPT_DIZIN / "19_gercek_onnx_celery_sure.py"
)
sure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sure)

AYARLAR = {
    "soft_limit": 600, "hard_limit": 660, "visibility_timeout": 900,
    "acks_late": True, "prefetch": 1, "store_floor": 0.05,
    "onnx_model_path": "/models/model512_best.onnx", "timing_log": "/app/media/z.jsonl",
}


def kayit(frame_id, taban=1.0, soguk=False, sira=1, tespit=2, **degisiklik):
    """Iscinin yazdigi bir zamanlama satirinin sentetik esdegeri."""
    veri = {
        "frame_id": frame_id, "run_id": 7, "durum": "done", "hata_sinifi": "",
        "kuyruk_bekleme": taban * 0.1, "goruntu_okuma": taban * 0.5,
        "karolama": taban * 0.01, "onnx_cikarim": taban * 2.0,
        "nms_koordinat": taban * 0.05, "db_yazma": taban * 0.02,
        "frame_toplam": taban * 3.0, "uctan_uca_sure": taban * 3.1,
        "tespit_sayisi": tespit, "karo_sayisi": 80,
        "soguk_baslangic": soguk, "oturum_kurulum_suresi": 0.4 if soguk else 0.0,
        "surec_kare_sirasi": sira,
    }
    veri.update(degisiklik)
    return veri


def kosu_ozeti(kare_sayisi=3):
    return {
        "gorev_id": 11, "gorev_adi": "olcum-test", "kosu_id": 7,
        "model_surumu": "model512-onnx", "kare_sayisi": kare_sayisi,
        "alinan": [{"frame_id": i, "dosya": f"k{i}.jpg", "kopya": False}
                   for i in range(1, kare_sayisi + 1)],
    }


def kare_bilgisi(kare_sayisi=3):
    return {i: {"goreli_yol": f"data/heridal/test/images/k{i}.jpg", "durum": "done"}
            for i in range(1, kare_sayisi + 1)}


def db_ozeti(kare=3, tespit=6, durumlar=None):
    return {
        "durumlar": durumlar or {"done": kare},
        "frame_sayisi": kare, "tespit_sayisi": tespit, "kosu_durumu": "done",
        "frames_done": kare, "frames_failed": 0, "frames_total": kare,
        "model_surumu": "model512-onnx", "cerceve": "onnx",
    }


# --- Ozet istatistikleri ------------------------------------------------------


def test_yuzdelik_ve_medyan_bilinen_degerlerde():
    """Yuzdelik ve medyan elle hesaplanabilir kucuk dizilerde dogru olmali."""
    assert sure.medyan([1, 2, 3]) == 2
    assert sure.medyan([1, 2, 3, 4]) == pytest.approx(2.5)
    assert sure.yuzdelik([1, 2, 3, 4, 5], 0.95) == pytest.approx(4.8)
    assert sure.yuzdelik([5], 0.95) == 5
    assert sure.yuzdelik([], 0.95) == 0.0


def test_ozet_degerleri_ham_satirlardan_uretiliyor():
    """Minimum, medyan, p95 ve maksimum kare CSV satirlarindan gelmeli."""
    kayitlar = [kayit(1, 1.0), kayit(2, 2.0), kayit(3, 3.0)]
    kare = sure.kare_satirlari(kayitlar, kare_bilgisi(), kosu_ozeti())
    ozet = {s["olcu"]: s for s in sure.ozet_satirlari(kare)}

    frame = ozet["frame_toplam"]
    assert frame["olcum_sayisi"] == 3
    assert frame["minimum"] == pytest.approx(3.0)
    assert frame["medyan"] == pytest.approx(6.0)
    assert frame["maksimum"] == pytest.approx(9.0)
    assert frame["p95"] == pytest.approx(sure.yuzdelik([3.0, 6.0, 9.0], 0.95), abs=1e-4)


def test_kare_ve_ozet_toplamlari_uyusuyor():
    """Ozetteki olcum sayisi kare satiri sayisina esit olmali."""
    kayitlar = [kayit(i, float(i)) for i in range(1, 6)]
    kare = sure.kare_satirlari(kayitlar, kare_bilgisi(5), kosu_ozeti(5))
    for satir in sure.ozet_satirlari(kare):
        assert satir["olcum_sayisi"] == len(kare)


def test_soguk_baslangic_ayri_isaretleniyor():
    """Ilk kare soguk, sonrakiler degil; oturum kurulumu yalniz ilk karede."""
    kayitlar = [kayit(1, 3.0, soguk=True, sira=1), kayit(2, 1.0, soguk=False, sira=2)]
    kare = {s["frame_id"]: s for s in sure.kare_satirlari(kayitlar, kare_bilgisi(2), kosu_ozeti(2))}
    assert kare[1]["soguk_baslangic"] == "evet"
    assert kare[2]["soguk_baslangic"] == "hayir"
    assert float(kare[1]["oturum_kurulum_suresi"]) > 0
    assert float(kare[2]["oturum_kurulum_suresi"]) == 0.0


def test_eksik_asama_suresi_olculmedi_yaziliyor_ve_kapiyi_kapatiyor():
    """Eksik alan sessizce 0 sayilmaz; 'olculmedi' yazilir ve kapi kapanir."""
    eksik = kayit(1)
    del eksik["db_yazma"]
    kare = sure.kare_satirlari([eksik], kare_bilgisi(1), kosu_ozeti(1))
    assert kare[0]["db_yazma"] == "olculmedi"

    kontrol = sure.kapi_kontrolleri(
        kare, db_ozeti(kare=1, tespit=2), kosu_ozeti(1), AYARLAR,
        {"disk": "a", "kayit": "a"}, 1,
    )
    eksik_kontrol = next(s for s in kontrol if s["kontrol"] == "eksik sure alani")
    assert eksik_kontrol["sonuc"] == "GECMEDI"


def test_negatif_sure_kapiyi_kapatiyor():
    """Monoton saatten gelen sure negatif olamaz; olursa kapi kapanir."""
    kare = sure.kare_satirlari([kayit(1, db_yazma=-0.5)], kare_bilgisi(1), kosu_ozeti(1))
    kontrol = sure.kapi_kontrolleri(
        kare, db_ozeti(kare=1, tespit=2), kosu_ozeti(1), AYARLAR,
        {"disk": "a", "kayit": "a"}, 1,
    )
    assert next(s for s in kontrol if s["kontrol"] == "negatif sure")["sonuc"] == "GECMEDI"


# --- Kapi kurallari -----------------------------------------------------------


def tam_kapi(kayitlar, db=None, beklenen=3):
    kare = sure.kare_satirlari(kayitlar, kare_bilgisi(beklenen), kosu_ozeti(beklenen))
    return sure.kapi_kontrolleri(
        kare, db or db_ozeti(kare=beklenen, tespit=sum(k["tespit_sayisi"] for k in kayitlar)),
        kosu_ozeti(beklenen), AYARLAR, {"disk": "a", "kayit": "a"}, beklenen,
    )


def test_saglikli_kosuda_butun_kontroller_geciyor():
    """Gercek dedektor, tam kayit ve oturum yeniden kullanimi varsa kapi acik."""
    kayitlar = [kayit(1, 3.0, soguk=True, sira=1), kayit(2, 1.0, sira=2), kayit(3, 1.0, sira=3)]
    assert all(s["sonuc"] == "GECTI" for s in tam_kapi(kayitlar))


def test_sahte_dedektor_kapiyi_kapatiyor():
    """framework 'fake' ise A kapisi gecmez."""
    db = db_ozeti(kare=3, tespit=6)
    db["cerceve"] = "fake"
    kontrol = tam_kapi([kayit(1, soguk=True, sira=1), kayit(2, sira=2), kayit(3, sira=3)], db)
    assert next(s for s in kontrol if s["kontrol"] == "gercek dedektor (framework)")["sonuc"] == "GECMEDI"


def test_takili_kare_kapiyi_kapatiyor():
    """Son duruma ulasmayan kare varsa kapi gecmez."""
    db = db_ozeti(kare=3, tespit=6, durumlar={"done": 2, "processing": 1})
    kontrol = tam_kapi([kayit(1, soguk=True, sira=1), kayit(2, sira=2), kayit(3, sira=3)], db)
    assert next(s for s in kontrol if s["kontrol"] == "son duruma ulasmayan kare")["sonuc"] == "GECMEDI"


def test_eksik_olcum_satiri_kapiyi_kapatiyor():
    """Kare sayisi kadar olcum satiri yoksa kapi gecmez."""
    kontrol = tam_kapi([kayit(1, soguk=True, sira=1), kayit(2, sira=2)])
    assert next(s for s in kontrol if s["kontrol"] == "olcum satiri = frame")["sonuc"] == "GECMEDI"


def test_csv_tespit_toplami_veritabaniyla_uyusmazsa_kapi_kapaniyor():
    """CSV toplami veritabanindan farkliysa kapi gecmez."""
    db = db_ozeti(kare=3, tespit=99)
    kontrol = tam_kapi([kayit(1, soguk=True, sira=1), kayit(2, sira=2), kayit(3, sira=3)], db)
    assert next(s for s in kontrol if s["kontrol"].startswith("CSV tespit"))["sonuc"] == "GECMEDI"


def test_her_kare_soguk_baslangicsa_oturum_yeniden_kullanilmamis_sayiliyor():
    """Her karede yeni oturum kurulmussa oturum paylasimi kontrolu gecmez."""
    kayitlar = [kayit(i, soguk=True, sira=1) for i in (1, 2, 3)]
    kontrol = tam_kapi(kayitlar)
    assert next(s for s in kontrol if s["kontrol"].startswith("oturum yeniden"))["sonuc"] == "GECMEDI"
    assert next(s for s in kontrol if s["kontrol"].startswith("surec kare sirasi"))["sonuc"] == "GECMEDI"


def test_model_hashi_uyusmazsa_kapi_kapaniyor():
    """Diskteki model export kaydiyla ayni degilse kapi gecmez."""
    kare = sure.kare_satirlari([kayit(1, soguk=True, sira=1)], kare_bilgisi(1), kosu_ozeti(1))
    kontrol = sure.kapi_kontrolleri(
        kare, db_ozeti(kare=1, tespit=2), kosu_ozeti(1), AYARLAR,
        {"disk": "aaa", "kayit": "bbb"}, 1,
    )
    assert next(s for s in kontrol if s["kontrol"] == "model sha256")["sonuc"] == "GECMEDI"


# --- Zaman asimi karari -------------------------------------------------------


def test_mevcut_limitler_yeterliyse_korunuyor():
    """Kuralin gerektirdiginden buyuk limitler sirf degistirmek icin dusurulmez."""
    kare = sure.kare_satirlari(
        [kayit(1, 3.0, soguk=True, sira=1), kayit(2, 1.0, sira=2)], kare_bilgisi(2), kosu_ozeti(2)
    )
    karar = sure.zaman_asimi_karari(kare, AYARLAR)
    assert karar["karar"] == "KORUNDU"
    assert karar["onerilen_soft_limit"] == AYARLAR["soft_limit"]
    assert karar["onerilen_hard_limit"] == AYARLAR["hard_limit"]
    assert karar["onerilen_visibility_timeout"] == AYARLAR["visibility_timeout"]
    assert karar["karar_gerekcesi"].strip() != ""


def test_limitler_yetersizse_yeni_deger_oneriliyor():
    """Olculen sure limitlere yaklasirsa kural yeni degerler uretir."""
    yavas = sure.kare_satirlari([kayit(1, 100.0, soguk=True, sira=1)], kare_bilgisi(1), kosu_ozeti(1))
    karar = sure.zaman_asimi_karari(yavas, AYARLAR)
    assert karar["karar"] == "GUNCELLENDI"
    assert karar["onerilen_soft_limit"] > AYARLAR["soft_limit"]


def test_karar_siralamasi_soft_hard_visibility():
    """Onerilen degerlerde soft < hard < visibility kurali korunmali."""
    for taban in (1.0, 10.0, 100.0):
        kare = sure.kare_satirlari([kayit(1, taban, soguk=True, sira=1)], kare_bilgisi(1), kosu_ozeti(1))
        karar = sure.zaman_asimi_karari(kare, AYARLAR)
        assert karar["onerilen_soft_limit"] < karar["onerilen_hard_limit"]
        assert karar["onerilen_hard_limit"] < karar["onerilen_visibility_timeout"]


def test_guvenlik_payi_karar_olarak_isaretleniyor():
    """Guvenlik payi olcum degil karar olarak kaydedilmeli."""
    kare = sure.kare_satirlari([kayit(1, 1.0, soguk=True, sira=1)], kare_bilgisi(1), kosu_ozeti(1))
    karar = sure.zaman_asimi_karari(kare, AYARLAR)
    assert karar["guvenlik_payi_notu"] == "KARAR (olcum degil)"
    assert karar["guvenlik_payi_turu"] == "carpan"
    assert karar["guvenlik_payi_degeri"] == sure.GUVENLIK_PAYI_DEGERI


def test_referans_sure_soguk_baslangici_iceriyor():
    """Referans sure, soguk baslangicli en yavas kareyi disarida birakmamali."""
    kare = sure.kare_satirlari(
        [kayit(1, 5.0, soguk=True, sira=1), kayit(2, 1.0, sira=2)], kare_bilgisi(2), kosu_ozeti(2)
    )
    karar = sure.zaman_asimi_karari(kare, AYARLAR)
    en_yavas = max(float(s["uctan_uca_sure"]) for s in kare)
    assert karar["olculen_referans_sure"] == pytest.approx(en_yavas, abs=1e-3)


def test_zorunlu_metadata_csvde():
    """Iki CSV de kosu komutu, tarihi ve model kimligini tasimali."""
    kare = sure.kare_satirlari([kayit(1, 1.0, soguk=True, sira=1)], kare_bilgisi(1), kosu_ozeti(1))
    kosu = sure.kosu_bilgisi(
        model_surumu="model512-onnx", onnx_sha256="abc", olcum_yolu="gercek Celery kuyrugu"
    )
    import tempfile

    with tempfile.TemporaryDirectory() as gecici:
        yol = sure.csv_yaz(Path(gecici) / "kare.csv", kare, kosu)
        satir = list(csv.DictReader(yol.open(encoding="utf-8")))[0]
        for alan in ("kosu_komut", "kosu_tarih", "kosu_surum_python",
                     "kosu_model_surumu", "kosu_onnx_sha256", "kosu_olcum_yolu"):
            assert satir[alan]
