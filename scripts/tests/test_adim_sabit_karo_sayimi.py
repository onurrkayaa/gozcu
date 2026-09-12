"""16_adim_sabit_karo_sayimi.py icindeki adim, karo sinifi ve hedef sayimlarinin
testleri.

Testler gercek egitim kumesine ve data/karo_* klasorlerine dokunmaz: her test
kendi kucuk goruntu/etiket kumesini gecici klasorde kurar. Karo geometrisi
kucuk tutulur ki hangi karonun hangi hedefi gordugu elle dogrulanabilsin.
"""

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

PROJE_KOK = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIZIN = PROJE_KOK / "scripts"

# Dosya adlari rakamla basladigi icin normal import edilemez; yoldan yukluyoruz.
sys.path.insert(0, str(SCRIPT_DIZIN))
sys.path.insert(0, str(PROJE_KOK / "backend"))

_spec = importlib.util.spec_from_file_location(
    "adim_sabit", SCRIPT_DIZIN / "16_adim_sabit_karo_sayimi.py"
)
sayim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sayim)

from core.tiling import karolari_hesapla  # noqa: E402

# Test geometrisi: 260x100 goruntu, 100 px karo, 0.2 ortusme (adim 80).
# Karolar: (0-100), (80-180), (160-260); hepsi y ekseninde tam boy.
KARO = 100
ORTUSME = 0.2
GORUNTU_OLCU = (260, 100)
BOLUM = ("train",)

# Deney kosullarinin beklenen ortak adimi.
DENEY_ADIMI = 240


def veri_kur(kok: Path, bolum: str, ad: str, kutular: list[tuple]) -> Path:
    """Gecici veri kumesine bir goruntu ve piksel kutulardan YOLO etiketi yazar."""
    from PIL import Image

    goruntu_dizin = kok / bolum / "images"
    etiket_dizin = kok / bolum / "labels"
    goruntu_dizin.mkdir(parents=True, exist_ok=True)
    etiket_dizin.mkdir(parents=True, exist_ok=True)

    genislik, yukseklik = GORUNTU_OLCU
    Image.new("RGB", (genislik, yukseklik), (30, 30, 30)).save(goruntu_dizin / f"{ad}.jpg")

    satirlar = [
        f"0 {(x1 + x2) / 2 / genislik:.6f} {(y1 + y2) / 2 / yukseklik:.6f} "
        f"{(x2 - x1) / genislik:.6f} {(y2 - y1) / yukseklik:.6f}"
        for x1, y1, x2, y2 in kutular
    ]
    (etiket_dizin / f"{ad}.txt").write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    return goruntu_dizin / f"{ad}.jpg"


def say(kok: Path):
    return sayim.kosulu_say(kok, KARO, ORTUSME, bolumler=BOLUM)


def dosya_kumesi(kok: Path) -> set:
    return {p.relative_to(kok) for p in kok.rglob("*")}


# --- Adim ---------------------------------------------------------------------


def test_iki_deney_kosulunun_adimi_240_px():
    """Karo 320/0,25 ve karo 512/0,53125 ayni adimi vermeli."""
    adimlar = [sayim.adim_piksel(karo, ortusme) for karo, ortusme in sayim.KOSULLAR]
    assert adimlar == [DENEY_ADIMI, DENEY_ADIMI]
    assert len(set(adimlar)) == 1


def test_adim_mevcut_karolama_ciktisiyla_tutarli():
    """Adim, karolari_hesapla'nin urettigi ardisik karolar arasindaki mesafeye esit."""
    for karo, ortusme in sayim.KOSULLAR:
        karolar = karolari_hesapla(karo * 4, karo, karo, ortusme)
        assert karolar[1][2] - karolar[0][2] == sayim.adim_piksel(karo, ortusme)


def test_mevcut_karolama_islevi_kullaniliyor(tmp_path, monkeypatch):
    """Karolama backend'deki islevden gelir ve plan gecisi 11'den cagrilir."""
    assert sayim.KARO_VERI.karolari_hesapla is karolari_hesapla

    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30)])
    cagrildi = []
    gercek = sayim.KARO_VERI.bolumu_planla
    monkeypatch.setattr(
        sayim.KARO_VERI, "bolumu_planla",
        lambda *a, **k: (cagrildi.append(a) or gercek(*a, **k)),
    )
    say(tmp_path)
    assert cagrildi, "11_karo_veri_hazirla.bolumu_planla cagrilmadi"


# --- Sayim kipi dosya yazmiyor ------------------------------------------------


def test_sayim_kipi_goruntu_veya_etiket_yazmiyor(tmp_path, monkeypatch):
    """Sayim sirasinda hicbir yeni dosya olusmamali ve karo yazici cagrilmamali."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30), (90, 10, 110, 30)])

    def yazma(*_, **__):
        raise AssertionError("sayim kipinde karo yazilmamali")

    monkeypatch.setattr(sayim.KARO_VERI, "karolari_yaz", yazma)
    monkeypatch.setattr(sayim.KARO_VERI, "data_yaml_yaz", yazma)

    onceki = dosya_kumesi(tmp_path)
    say(tmp_path)
    assert dosya_kumesi(tmp_path) == onceki
    assert not (PROJE_KOK / "data" / f"karo_{KARO}").exists()


# --- Karo siniflari -----------------------------------------------------------


def test_pozitif_karo_dogru_siniflaniyor(tmp_path):
    """Tam iceride kalan hedefin karosu pozitif; kesismeyen karolar negatif aday."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30)])
    satir = say(tmp_path)
    assert satir["pozitif_karo"] == 1
    assert satir["belirsiz_karo"] == 0
    assert satir["negatif_aday_karo"] == 2
    assert satir["planlanan_toplam_karo"] == 3


def test_hedefle_kesismeyen_karo_negatif_aday(tmp_path):
    """Hicbir hedefle kesismeyen karo negatif aday sayilir."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30)])
    satir = say(tmp_path)
    assert satir["negatif_aday_karo"] == 2
    assert satir["pozitif_karo"] + satir["belirsiz_karo"] + satir["negatif_aday_karo"] == 3


def test_belirsiz_karo_negatif_sayilmiyor(tmp_path):
    """Icinde esigi gecemeyen hedef bulunan karo belirsizdir, negatif aday degildir."""
    # 240 px genisligindeki hedef uc karonun da en fazla %42'sine sigar.
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 250, 90)])
    satir = say(tmp_path)
    assert satir["belirsiz_karo"] == 3
    assert satir["negatif_aday_karo"] == 0
    assert satir["pozitif_karo"] == 0


# --- Hedef bazinda sayim ------------------------------------------------------


def test_bir_karoda_atlanan_baska_karoda_gecerli_hedef_kaybolmus_sayilmiyor(tmp_path):
    """Kenar hedefi bir karoda esigi gecemese de baska karoda butun kaliyorsa kaybolmaz."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(90, 10, 110, 30)])
    satir = say(tmp_path)
    assert satir["benzersiz_hedef_sayisi"] == 1
    assert satir["atlanan_hedef_ornegi_sayisi"] == 1
    assert satir["gecerli_karo_etiket_sayisi"] == 1
    assert satir["tamamen_kaybolan_benzersiz_hedef"] == 0
    assert satir["en_az_bir_gecerli_ornegi_olan_benzersiz_hedef"] == 1
    # Esigi gecemedigi karo belirsiz oldugu icin hedef o karoya dusmus sayilir.
    assert satir["en_az_bir_belirsiz_karoya_dusen_benzersiz_hedef"] == 1


def test_butun_karolarda_gecersiz_kalan_hedef_kaybolmus_sayiliyor(tmp_path):
    """Hicbir karoda %60 esigini gecemeyen hedef tamamen kaybolmus sayilir."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 250, 90)])
    satir = say(tmp_path)
    assert satir["tamamen_kaybolan_benzersiz_hedef"] == 1
    assert satir["en_az_bir_gecerli_ornegi_olan_benzersiz_hedef"] == 0
    assert satir["gecerli_karo_etiket_sayisi"] == 0
    assert satir["hedef_basina_gecerli_karo_etiket"] == 0.0


def test_benzersiz_hedefler_iki_kez_sayilmiyor(tmp_path):
    """Iki karoda birden gecerli olan hedef bir kez sayilir; karo-etiket iki olur."""
    # x 82-98: hem (0-100) hem (80-180) karosunun tamamen icinde.
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(82, 10, 98, 30)])
    satir = say(tmp_path)
    assert satir["benzersiz_hedef_sayisi"] == 1
    assert satir["gecerli_karo_etiket_sayisi"] == 2
    assert satir["hedef_basina_gecerli_karo_etiket"] == pytest.approx(2.0)
    assert satir["en_az_bir_gecerli_ornegi_olan_benzersiz_hedef"] == 1


def test_ayni_hedef_birden_cok_goruntude_ayri_sayiliyor(tmp_path):
    """Farkli goruntulerdeki hedefler ayri benzersiz hedeflerdir."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30)])
    veri_kur(tmp_path, "train", "train_ZRI_0002", [(10, 10, 30, 30)])
    assert say(tmp_path)["benzersiz_hedef_sayisi"] == 2


# --- Uretim davranisi, belirlenimcilik, metadata ------------------------------


def test_normal_veri_uretme_davranisi_degismiyor(tmp_path):
    """Sayim, uretim kosusunun plan gecisiyle birebir ayni karo sayilarini vermeli."""
    veri_kur(tmp_path, "train", "train_ZRI_0001",
             [(10, 10, 30, 30), (90, 10, 110, 30), (10, 10, 250, 90)])
    satir = say(tmp_path)
    plan = sayim.KARO_VERI.bolumu_planla(
        "train", tmp_path, KARO, ORTUSME, sayim.MIN_GORUNUR, 0
    )
    assert satir["pozitif_karo"] == len(plan["pozitifler"])
    assert satir["belirsiz_karo"] == len(plan["belirsizler"])
    assert satir["negatif_aday_karo"] == len(plan["negatif_adaylar"])
    assert satir["atlanan_hedef_ornegi_sayisi"] == plan["atlanan_etiket"]
    assert satir["gecerli_karo_etiket_sayisi"] == sum(len(e) for *_, e in plan["pozitifler"])
    assert satir["tamamen_kaybolan_benzersiz_hedef"] == len(plan["butun_kalmayan"])
    # Uretim yolu oldugu gibi duruyor.
    for ad in ("bolumu_planla", "karolari_yaz", "data_yaml_yaz", "main"):
        assert hasattr(sayim.KARO_VERI, ad)


def test_ayni_girdi_ayni_sirali_sonucu_uretiyor(tmp_path):
    """Iki kez calistirilan sayim birebir ayni satiri vermeli."""
    veri_kur(tmp_path, "train", "train_ZRI_0002", [(10, 10, 30, 30)])
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(90, 10, 110, 30)])
    assert say(tmp_path) == say(tmp_path)


def test_zorunlu_metadata_csvde_bulunuyor(tmp_path):
    """CSV her satirda kosu komutu, tarihi, surumu ve sayim kipini tasimali."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30)])
    kosu = sayim.kosu_bilgisi(
        bolumler="train,valid",
        min_gorunur=sayim.MIN_GORUNUR,
        sayim_kipi="yalnizca sayim; dosya yazilmadi",
        kaynak_script="scripts/16_adim_sabit_karo_sayimi.py",
    )
    yol = sayim.csv_yaz(tmp_path / "sonuc.csv", [say(tmp_path)], kosu)

    okunan = list(csv.DictReader(yol.open(encoding="utf-8")))
    assert okunan
    for satir in okunan:
        for alan in (
            "kosu_komut", "kosu_tarih", "kosu_surum_python", "kosu_bolumler",
            "kosu_min_gorunur", "kosu_sayim_kipi", "kosu_kaynak_script",
        ):
            assert satir[alan]


def test_sonuc_etiketi_iki_metrige_birden_bakiyor():
    """Bir kosul iki metrikte de olumsuzsa etiketlenir; yonler ayrilirsa KARISIK."""
    def satirlar(oran_a, ornek_a, oran_b, ornek_b):
        return [
            {"karo_boyutu": 320, "benzersiz_hedef_sayisi": 10,
             "belirsiz_karoya_dusen_hedef_orani": oran_a,
             "hedef_basina_gecerli_karo_etiket": ornek_a},
            {"karo_boyutu": 512, "benzersiz_hedef_sayisi": 10,
             "belirsiz_karoya_dusen_hedef_orani": oran_b,
             "hedef_basina_gecerli_karo_etiket": ornek_b},
        ]

    assert sayim.sonuc_etiketi(satirlar(0.4, 1.0, 0.2, 1.5))["etiket"] == \
        "KARO 320 DAHA FAZLA ETKILENIYOR"
    assert sayim.sonuc_etiketi(satirlar(0.2, 1.5, 0.4, 1.0))["etiket"] == \
        "KARO 512 DAHA FAZLA ETKILENIYOR"
    assert sayim.sonuc_etiketi(satirlar(0.4, 1.5, 0.2, 1.0))["etiket"] == "KARISIK SONUC"
    assert sayim.sonuc_etiketi(satirlar(0.3, 1.2, 0.3, 1.2))["etiket"] == "ESIT"
