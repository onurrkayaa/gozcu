"""15_kenar_kurali_yukseklik.py icindeki bant, kimlik ve kenar kurali sayimlarinin
testleri.

Testler gercek egitim kumesine dokunmaz: her test kendi kucuk goruntu/etiket
kumesini gecici klasorde kurar. Karo geometrisi kucuk tutulur ki hangi karonun
hangi hedefi gordugu elle dogrulanabilsin.
"""

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

PROJE_KOK = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIZIN = PROJE_KOK / "scripts"

# Dosya adi rakamla basladigi icin normal import edilemez; yoldan yukluyoruz.
# scripts/ ve backend/ yola ekleniyor ki modulun kendi importlari (ortak,
# core.tiling, 11_karo_veri_hazirla) cozulebilsin.
sys.path.insert(0, str(SCRIPT_DIZIN))
sys.path.insert(0, str(PROJE_KOK / "backend"))

_spec = importlib.util.spec_from_file_location(
    "kenar_kurali", SCRIPT_DIZIN / "15_kenar_kurali_yukseklik.py"
)
kenar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kenar)

# Test geometrisi: 260x100 goruntu, 100 px karo, 0.2 ortusme (adim 80).
# Karolar: (0-100), (80-180), (160-260); hepsi y ekseninde tam boy.
KARO = 100
ORTUSME = 0.2
MIN_GORUNUR = 0.6
GORUNTU_OLCU = (260, 100)

BANT_ETIKETLERI = ["<44", "44-55", "55-65", "65-80", ">=80"]


def bant_csv_yaz(kok: Path) -> Path:
    """yukseklik_kazanim.csv ile ayni sutun adini tasiyan kucuk bir bant dosyasi."""
    yol = kok / "bantlar.csv"
    with yol.open("w", newline="", encoding="utf-8") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=["grup", "yukseklik_bandi_px"])
        yazici.writeheader()
        for etiket in BANT_ETIKETLERI:
            yazici.writerow({"grup": "TOPLAM", "yukseklik_bandi_px": etiket})
    return yol


def bantlar(tmp_path: Path):
    return kenar.bant_sinirlari(bant_csv_yaz(tmp_path))


def veri_kur(kok: Path, bolum: str, ad: str, kutular: list[tuple]) -> Path:
    """Gecici veri kumesine bir goruntu ve piksel kutulardan YOLO etiketi yazar."""
    from PIL import Image

    goruntu_dizin = kok / bolum / "images"
    etiket_dizin = kok / bolum / "labels"
    goruntu_dizin.mkdir(parents=True, exist_ok=True)
    etiket_dizin.mkdir(parents=True, exist_ok=True)

    genislik, yukseklik = GORUNTU_OLCU
    Image.new("RGB", (genislik, yukseklik), (30, 30, 30)).save(goruntu_dizin / f"{ad}.jpg")

    satirlar = []
    for x1, y1, x2, y2 in kutular:
        satirlar.append(
            f"0 {(x1 + x2) / 2 / genislik:.6f} {(y1 + y2) / 2 / yukseklik:.6f} "
            f"{(x2 - x1) / genislik:.6f} {(y2 - y1) / yukseklik:.6f}"
        )
    (etiket_dizin / f"{ad}.txt").write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    return goruntu_dizin / f"{ad}.jpg"


def izle(kok: Path, bolumler=("train",)):
    return kenar.hedefleri_izle(
        kok, KARO, ORTUSME, MIN_GORUNUR, bantlar(kok), bolumler=bolumler
    )


# --- Hedef kimligi ------------------------------------------------------------


def test_iki_etiket_satiri_ayni_kimligi_almiyor(tmp_path):
    """Ayni goruntudeki iki etiket satiri farkli hedef kimligi almali."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30), (40, 10, 60, 30)])
    kayitlar = izle(tmp_path)
    kimlikler = [k["hedef_kimligi"] for k in kayitlar]
    assert len(kimlikler) == 2
    assert len(set(kimlikler)) == 2


def test_kimlik_bolum_yol_ve_satir_numarasindan_olusuyor(tmp_path):
    """Ayni dosya adi farkli bolumdeyse kimlikler yine ayrisir."""
    veri_kur(tmp_path, "train", "ayni_ad", [(10, 10, 30, 30)])
    veri_kur(tmp_path, "valid", "ayni_ad", [(10, 10, 30, 30)])
    kayitlar = izle(tmp_path, bolumler=("train", "valid"))
    assert len({k["hedef_kimligi"] for k in kayitlar}) == 2
    assert kenar.hedef_kimligi("train", "train/images/a.jpg", 1) != \
        kenar.hedef_kimligi("train", "train/images/a.jpg", 2)


# --- Bant yerlestirme ---------------------------------------------------------


def test_bant_sinirlari_csvden_okunuyor(tmp_path):
    """Bant etiketleri CSV'deki bicimiyle cozulmeli ve alt sinira gore siralanmali."""
    cozulen = kenar.bant_sinirlari(bant_csv_yaz(tmp_path))
    assert [e for e, _, _ in cozulen] == BANT_ETIKETLERI
    assert cozulen[-1][1] == 80.0


@pytest.mark.parametrize("yukseklik,beklenen", [
    (10.0, "<44"), (43.9, "<44"), (44.0, "44-55"), (54.9, "44-55"),
    (55.0, "55-65"), (65.0, "65-80"), (79.9, "65-80"), (80.0, ">=80"), (300.0, ">=80"),
])
def test_hedef_yuksekligi_dogru_banda_giriyor(tmp_path, yukseklik, beklenen):
    """Ust sinir haric tutulur: 80.0 px alt banda degil, >=80 bandina girer."""
    assert kenar.bandi_bul(yukseklik, bantlar(tmp_path)) == beklenen


def test_izlenen_hedefin_bandi_kutu_yuksekligiyle_tutarli(tmp_path):
    """Etiketten okunan kutu yuksekligi ile yazilan bant ayni olmali."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 90)])
    kayit = izle(tmp_path)[0]
    assert kayit["kutu_yukseklik_px"] == pytest.approx(80.0, abs=0.2)
    assert kayit["yukseklik_bandi"] == ">=80"


# --- Kenar kurali sayimlari ---------------------------------------------------


def test_tamamen_karo_icindeki_hedef_gecerli(tmp_path):
    """Tek karonun tamamen icinde kalan hedef o karoda gecerli sayilir, atlanan yok."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30)])
    kayit = izle(tmp_path)[0]
    assert kayit["kesisen_karo"] == 1
    assert kayit["gecerli_karo_etiket"] == 1
    assert kayit["atlanan_hedef_ornegi"] == 0
    assert kayit["kenar_kuralindan_etkilendi"] is False
    assert kayit["en_az_bir_gecerli_ornek"] is True
    assert kayit["tamamen_kayboldu"] is False


def test_esik_altindaki_kesisim_atlanan_ornek_sayiliyor(tmp_path):
    """Karoda yalnizca %50'si gorunen hedef o karoda atlanan ornek sayilir."""
    # x 90-110: birinci karoda (0-100) yarisi gorunur -> %50 < %60.
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(90, 10, 110, 30)])
    kayit = izle(tmp_path)[0]
    assert kayit["atlanan_hedef_ornegi"] == 1
    assert kayit["kenar_kuralindan_etkilendi"] is True


def test_bir_karoda_atlanan_baska_karoda_gecerli_hedef_kaybolmus_sayilmiyor(tmp_path):
    """Ayni hedef bir karoda esigi gecemese de baska karoda butun kaliyorsa kaybolmaz."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(90, 10, 110, 30)])
    kayit = izle(tmp_path)[0]
    assert kayit["kesisen_karo"] == 2
    assert kayit["gecerli_karo_etiket"] == 1   # ikinci karoda (80-180) tam iceride
    assert kayit["atlanan_hedef_ornegi"] == 1
    assert kayit["tamamen_kayboldu"] is False
    assert kayit["en_az_bir_gecerli_ornek"] is True


def test_butun_karolarda_gecersiz_kalan_hedef_kaybolmus_sayiliyor(tmp_path):
    """Hicbir karoda %60 esigini gecemeyen hedef tamamen kaybolmus sayilir."""
    # 240 px genisligindeki hedef uc karonun da en fazla %42'sine sigar.
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 250, 90)])
    kayit = izle(tmp_path)[0]
    assert kayit["kesisen_karo"] == 3
    assert kayit["gecerli_karo_etiket"] == 0
    assert kayit["atlanan_hedef_ornegi"] == 3
    assert kayit["tamamen_kayboldu"] is True
    assert kayit["en_az_bir_gecerli_ornek"] is False


# --- Bant toplamlari ----------------------------------------------------------


def test_bant_toplamlari_genel_toplamla_uyusuyor(tmp_path):
    """Bant satirlarinin toplami TOPLAM satirina esit olmali."""
    veri_kur(tmp_path, "train", "train_ZRI_0001",
             [(10, 10, 30, 30), (90, 10, 110, 30), (10, 10, 250, 90)])
    veri_kur(tmp_path, "train", "train_VRD_0002", [(10, 20, 40, 95)])
    kayitlar = izle(tmp_path)
    satirlar = kenar.bant_satirlari(kayitlar, bantlar(tmp_path))

    bant_satir = [s for s in satirlar if s["yukseklik_bandi"] != "TOPLAM"]
    toplam = next(s for s in satirlar if s["yukseklik_bandi"] == "TOPLAM")
    for alan in (
        "benzersiz_hedef_sayisi", "toplam_kesisen_karo", "gecerli_karo_etiket_sayisi",
        "atlanan_hedef_ornegi_sayisi", "en_az_bir_kez_etkilenen_hedef_sayisi",
        "en_az_bir_gecerli_ornegi_olan_hedef_sayisi", "tamamen_kaybolan_hedef_sayisi",
    ):
        assert sum(s[alan] for s in bant_satir) == toplam[alan]
    assert toplam["benzersiz_hedef_sayisi"] == len(kayitlar)


def test_oranlar_sayimlardan_hesaplaniyor(tmp_path):
    """Oran sutunlari ayni satirdaki sayimlarla tutarli olmali."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30), (90, 10, 110, 30)])
    toplam = next(
        s for s in kenar.bant_satirlari(izle(tmp_path), bantlar(tmp_path))
        if s["yukseklik_bandi"] == "TOPLAM"
    )
    # Oranlar projenin geri kalaninda oldugu gibi 4 basamaga yuvarlanir.
    yuvarlama = 5e-5
    assert toplam["hedef_basina_gecerli_ornek"] == pytest.approx(
        toplam["gecerli_karo_etiket_sayisi"] / toplam["benzersiz_hedef_sayisi"],
        abs=yuvarlama)
    assert toplam["etkilenen_hedef_orani"] == pytest.approx(
        toplam["en_az_bir_kez_etkilenen_hedef_sayisi"] / toplam["benzersiz_hedef_sayisi"],
        abs=yuvarlama)
    assert toplam["atlanan_ornek_orani"] == pytest.approx(
        toplam["atlanan_hedef_ornegi_sayisi"] / toplam["toplam_kesisen_karo"],
        abs=yuvarlama)


# --- Belirlenimcilik ve metadata ----------------------------------------------


def test_ayni_girdi_ayni_sirali_ciktiyi_uretiyor(tmp_path):
    """Iki kez calistirilan analiz birebir ayni satirlari ayni sirada vermeli."""
    veri_kur(tmp_path, "train", "train_ZRI_0002", [(10, 10, 30, 30)])
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(90, 10, 110, 30)])
    veri_kur(tmp_path, "valid", "valid_VRD_0003", [(10, 10, 250, 90)])

    birinci = izle(tmp_path, bolumler=("train", "valid"))
    ikinci = izle(tmp_path, bolumler=("train", "valid"))
    assert birinci == ikinci
    assert kenar.bant_satirlari(birinci, bantlar(tmp_path)) == \
        kenar.bant_satirlari(ikinci, bantlar(tmp_path))
    # Bant sirasi CSV'deki sira, sonda TOPLAM.
    sira = [s["yukseklik_bandi"] for s in kenar.bant_satirlari(birinci, bantlar(tmp_path))]
    assert sira == BANT_ETIKETLERI + ["TOPLAM"]


def test_zorunlu_metadata_csvde_bulunuyor(tmp_path):
    """CSV her satirda kosu komutu, tarihi, surumu ve karo parametrelerini tasimali."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30)])
    satirlar = kenar.bant_satirlari(izle(tmp_path), bantlar(tmp_path))
    kosu = kenar.kosu_bilgisi(
        karo_boyutu=KARO,
        ortusme_orani=ORTUSME,
        ortusme_piksel=20,
        min_gorunur=MIN_GORUNUR,
        bolumler="train,valid",
        kaynak_manifest="reports/karo_veri_manifest_512.csv",
    )
    yol = kenar.csv_yaz(tmp_path / "kenar.csv", satirlar, kosu)

    okunan = list(csv.DictReader(yol.open(encoding="utf-8")))
    assert okunan
    for satir in okunan:
        for alan in (
            "kosu_komut", "kosu_tarih", "kosu_surum_python", "kosu_karo_boyutu",
            "kosu_ortusme_orani", "kosu_min_gorunur", "kosu_bolumler",
            "kosu_kaynak_manifest",
        ):
            assert satir[alan]


# --- Capraz kontrol ve hipotez karari -----------------------------------------


def test_capraz_kontrol_uyusmazligi_bildiriyor(tmp_path):
    """Mevcut kayittan sapan her olcu UYUSMADI olarak isaretlenmeli."""
    veri_kur(tmp_path, "train", "train_ZRI_0001", [(10, 10, 30, 30)])
    kayitlar = izle(tmp_path)
    mevcut = {
        "benzersiz_hedef": 1, "gecerli_karo_etiket": 1,
        "atlanan_hedef_ornegi": 0, "tamamen_kaybolan_hedef": 0,
    }
    assert all(s["sonuc"] == "UYUSTU" for s in kenar.capraz_kontrol(kayitlar, mevcut))

    mevcut["gecerli_karo_etiket"] = 99
    sapan = [s for s in kenar.capraz_kontrol(kayitlar, mevcut) if s["sonuc"] == "UYUSMADI"]
    assert len(sapan) == 1
    assert sapan[0]["mevcut_kayit"] == 99 and sapan[0]["yeni_analiz"] == 1


def test_hipotez_karari_iki_metrige_birden_bakiyor(tmp_path):
    """Son bant iki metrikte de olumsuzsa DESTEKLENDI, tek metrikte olumsuzsa KARISIK."""
    bant = bantlar(tmp_path)
    onceki, son = bant[-2][0], bant[-1][0]

    def satirlar(oran_son, ornek_son):
        return [
            {"yukseklik_bandi": onceki, "benzersiz_hedef_sayisi": 10,
             "etkilenen_hedef_orani": 0.2, "hedef_basina_gecerli_ornek": 1.5},
            {"yukseklik_bandi": son, "benzersiz_hedef_sayisi": 10,
             "etkilenen_hedef_orani": oran_son, "hedef_basina_gecerli_ornek": ornek_son},
        ]

    assert kenar.hipotez_karari(satirlar(0.5, 1.0), bant)["karar"] == "DESTEKLENDI"
    assert kenar.hipotez_karari(satirlar(0.1, 2.0), bant)["karar"] == "CURUTULDU"
    assert kenar.hipotez_karari(satirlar(0.5, 2.0), bant)["karar"] == "KARISIK SONUC"
