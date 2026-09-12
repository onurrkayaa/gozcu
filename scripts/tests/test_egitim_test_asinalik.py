"""14_egitim_test_asinalik.py icindeki hash, sayim ve kesisim mantiginin testleri.

Testler gercek veri kumesine dokunmaz: her test kendi gecici train/valid/test
klasorunu kurar. Goruntu dosyalari acilmadigi icin icerikleri duz bayt olabilir.
"""

import csv
import importlib.util
import sys
from pathlib import Path

PROJE_KOK = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIZIN = PROJE_KOK / "scripts"

# Dosya adi rakamla basladigi icin normal import edilemez; yoldan yukluyoruz.
sys.path.insert(0, str(SCRIPT_DIZIN))

_spec = importlib.util.spec_from_file_location(
    "asinalik", SCRIPT_DIZIN / "14_egitim_test_asinalik.py"
)
asinalik = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(asinalik)

# Gecerli tek bir YOLO etiket satiri.
ETIKET_SATIRI = "0 0.5 0.5 0.02 0.02"


def goruntu_yaz(veri_kok: Path, bolum: str, ad: str, icerik: bytes, hedef: int) -> Path:
    """Gecici veri kumesine bir goruntu ve etiketini yazar."""
    goruntu_dizin = veri_kok / bolum / "images"
    etiket_dizin = veri_kok / bolum / "labels"
    goruntu_dizin.mkdir(parents=True, exist_ok=True)
    etiket_dizin.mkdir(parents=True, exist_ok=True)
    yol = goruntu_dizin / f"{ad}.jpg"
    yol.write_bytes(icerik)
    (etiket_dizin / f"{ad}.txt").write_text(
        "\n".join([ETIKET_SATIRI] * hedef), encoding="utf-8"
    )
    return yol


def bos_kume(veri_kok: Path) -> None:
    """Uc bolumu de var eder; bos kalanlar da klasor olarak bulunmali."""
    for bolum in asinalik.BOLUMLER:
        (veri_kok / bolum / "images").mkdir(parents=True, exist_ok=True)
        (veri_kok / bolum / "labels").mkdir(parents=True, exist_ok=True)


# --- SHA-256 ------------------------------------------------------------------


def test_ayni_baytlar_ayni_hash(tmp_path):
    """Adlari ve klasorleri farkli olsa da ayni bayt dizisi ayni ozeti vermeli."""
    a = tmp_path / "train_ZRI_0001.jpg"
    b = tmp_path / "test_VRD_9999.jpg"
    a.write_bytes(b"ayni-icerik")
    b.write_bytes(b"ayni-icerik")
    assert asinalik.dosya_sha256(a) == asinalik.dosya_sha256(b)


def test_farkli_baytlar_farkli_hash(tmp_path):
    """Tek bayt farki bile ozeti degistirmeli."""
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    a.write_bytes(b"icerik-1")
    b.write_bytes(b"icerik-2")
    assert asinalik.dosya_sha256(a) != asinalik.dosya_sha256(b)


def test_hash_dosya_adindan_degil_icerikten(tmp_path):
    """Ayni adin iki farkli icerigi ayni ozeti vermemeli: hash yol metninin degil,
    dosya baytlarinin ozetidir."""
    yol = tmp_path / "ayni_ad.jpg"
    yol.write_bytes(b"birinci")
    birinci = asinalik.dosya_sha256(yol)
    yol.write_bytes(b"ikinci")
    assert birinci != asinalik.dosya_sha256(yol)


# --- Sizinti ve onek ayrimi ---------------------------------------------------


def test_ayni_hash_train_ve_testteyse_sizinti(tmp_path):
    """Ayni bayt icerigi hem train hem testte ise veri_sizintisi isaretlenmeli."""
    bos_kume(tmp_path)
    goruntu_yaz(tmp_path, "train", "train_ZRI_0001", b"ortak-goruntu", 1)
    goruntu_yaz(tmp_path, "test", "test_ZRI_0002", b"ortak-goruntu", 1)

    satirlar = asinalik.hash_satirlari(asinalik.tum_kayitlar(tmp_path))
    sizan = [s for s in satirlar if s["veri_sizintisi"] == asinalik.EVET]
    assert len(sizan) == 1
    assert sizan[0]["train_test_eslesmesi"] == asinalik.EVET
    # Iki dosyanin da goreli yolu korunmali.
    assert sizan[0]["train_dosyalari"] == "train/images/train_ZRI_0001.jpg"
    assert sizan[0]["test_dosyalari"] == "test/images/test_ZRI_0002.jpg"


def test_ayni_onek_farkli_icerik_sizinti_degil(tmp_path):
    """Ayni kaynak onegi paylasan ama icerigi farkli dosyalar sizinti sayilmaz;
    onek kesisimi yine de raporlanir."""
    bos_kume(tmp_path)
    goruntu_yaz(tmp_path, "train", "train_ZRI_0001", b"egitim-goruntusu", 2)
    goruntu_yaz(tmp_path, "test", "test_ZRI_0002", b"test-goruntusu", 3)
    kayitlar = asinalik.tum_kayitlar(tmp_path)

    hashler = asinalik.hash_satirlari(kayitlar)
    assert all(s["veri_sizintisi"] == asinalik.HAYIR for s in hashler)
    assert all(s["train_test_eslesmesi"] == asinalik.HAYIR for s in hashler)

    onekler = asinalik.onek_satirlari(kayitlar)
    assert len(onekler) == 1
    assert onekler[0]["kaynak_oneki"] == "ZRI"
    assert onekler[0]["train_test_kesisimi"] == asinalik.EVET


def test_kesisim_olmasa_da_tum_hashler_yazilir(tmp_path):
    """Hic kesisim yoksa bile her benzersiz hash bir satir olmali."""
    bos_kume(tmp_path)
    goruntu_yaz(tmp_path, "train", "train_ZRI_0001", b"bir", 0)
    goruntu_yaz(tmp_path, "valid", "valid_BLI_0002", b"iki", 1)
    goruntu_yaz(tmp_path, "test", "test_VRD_0003", b"uc", 2)

    satirlar = asinalik.hash_satirlari(asinalik.tum_kayitlar(tmp_path))
    assert len(satirlar) == 3


# --- Hedef sayimi -------------------------------------------------------------


def test_hedef_sayilari_bolum_bolum_toplanir(tmp_path):
    """Her bolumun goruntu ve hedef sayisi etiket satirlarindan dogru toplanmali;
    bos etiket sifir hedef sayilir."""
    bos_kume(tmp_path)
    goruntu_yaz(tmp_path, "train", "train_ZRI_0001", b"t1", 3)
    goruntu_yaz(tmp_path, "train", "train_VRD_0002", b"t2", 0)
    goruntu_yaz(tmp_path, "valid", "valid_ZRI_0003", b"v1", 5)
    goruntu_yaz(tmp_path, "test", "test_VRD_0004", b"s1", 2)
    goruntu_yaz(tmp_path, "test", "test_VRD_0005", b"s2", 4)

    ozet = asinalik.bolum_ozeti(asinalik.tum_kayitlar(tmp_path))
    assert ozet["train"] == {"goruntu": 2, "hedef": 3, "onek": 2}
    assert ozet["valid"] == {"goruntu": 1, "hedef": 5, "onek": 1}
    assert ozet["test"] == {"goruntu": 2, "hedef": 6, "onek": 1}


def test_onek_satirlari_hedefleri_dogru_dagitir(tmp_path):
    """Onek kirilimindaki hedef sayilari bolum bolum dogru ayrilmali."""
    bos_kume(tmp_path)
    goruntu_yaz(tmp_path, "train", "train_ZRI_0001", b"t1", 3)
    goruntu_yaz(tmp_path, "valid", "valid_ZRI_0002", b"v1", 5)
    goruntu_yaz(tmp_path, "test", "test_VRD_0003", b"s1", 2)

    satirlar = {s["kaynak_oneki"]: s for s in asinalik.onek_satirlari(
        asinalik.tum_kayitlar(tmp_path))}
    assert satirlar["ZRI"]["train_hedef_sayisi"] == 3
    assert satirlar["ZRI"]["valid_hedef_sayisi"] == 5
    assert satirlar["ZRI"]["test_hedef_sayisi"] == 0
    assert satirlar["VRD"]["test_hedef_sayisi"] == 2
    assert satirlar["VRD"]["train_valid_kesisimi"] == asinalik.HAYIR


def test_bozuk_etiket_sessizce_gecilmiyor(tmp_path):
    """Eksik alani olan bir etiket satiri hata firlatmali; dosya adi hatada gecmeli."""
    bos_kume(tmp_path)
    goruntu_yaz(tmp_path, "train", "train_ZRI_0001", b"t1", 1)
    etiket = tmp_path / "train" / "labels" / "train_ZRI_0001.txt"
    etiket.write_text("0 0.5 0.5\n", encoding="utf-8")

    try:
        asinalik.hedef_say(etiket)
    except ValueError as hata:
        assert "train_ZRI_0001.txt" in str(hata)
    else:
        raise AssertionError("Bozuk etiket icin hata beklenmisti")


def test_eksik_etiket_sessizce_gecilmiyor(tmp_path):
    """Etiket dosyasi yoksa sifir hedef sayilmaz, hata firlatilir."""
    bos_kume(tmp_path)
    goruntu_yaz(tmp_path, "train", "train_ZRI_0001", b"t1", 1)
    (tmp_path / "train" / "labels" / "train_ZRI_0001.txt").unlink()

    try:
        asinalik.tum_kayitlar(tmp_path)
    except FileNotFoundError as hata:
        assert "train_ZRI_0001.txt" in str(hata)
    else:
        raise AssertionError("Eksik etiket icin hata beklenmisti")


# --- Belirlenimcilik ve metadata ----------------------------------------------


def test_cikti_sirasi_ayni_girdide_degismiyor(tmp_path):
    """Ayni veri kumesi iki kez taranirsa satir sirasi birebir ayni olmali."""
    bos_kume(tmp_path)
    for ad, icerik in (
        ("train_ZRI_0009", b"dokuz"), ("train_BLI_0001", b"bir"),
        ("train_VRD_0005", b"bes"),
    ):
        goruntu_yaz(tmp_path, "train", ad, icerik, 1)
    goruntu_yaz(tmp_path, "test", "test_ZRI_0100", b"yuz", 1)

    birinci = asinalik.tum_kayitlar(tmp_path)
    ikinci = asinalik.tum_kayitlar(tmp_path)
    assert birinci == ikinci
    assert asinalik.onek_satirlari(birinci) == asinalik.onek_satirlari(ikinci)
    assert asinalik.hash_satirlari(birinci) == asinalik.hash_satirlari(ikinci)
    # Onekler alfabetik, hash'ler ozet degerine gore sirali.
    onek_sirasi = [s["kaynak_oneki"] for s in asinalik.onek_satirlari(birinci)]
    assert onek_sirasi == sorted(onek_sirasi)
    hash_sirasi = [s["sha256"] for s in asinalik.hash_satirlari(birinci)]
    assert hash_sirasi == sorted(hash_sirasi)


def test_zorunlu_metadata_iki_csvde_de_var(tmp_path):
    """Iki CSV de kosu_komut, kosu_tarih ve python surumunu tasimali."""
    bos_kume(tmp_path)
    goruntu_yaz(tmp_path, "train", "train_ZRI_0001", b"t1", 1)
    goruntu_yaz(tmp_path, "test", "test_VRD_0002", b"s1", 1)
    kayitlar = asinalik.tum_kayitlar(tmp_path)

    kosu = asinalik.kosu_bilgisi(veri_kok=str(tmp_path))
    onek_csv = asinalik.csv_yaz(
        tmp_path / "onek.csv", asinalik.onek_satirlari(kayitlar), kosu)
    hash_csv = asinalik.csv_yaz(
        tmp_path / "hash.csv", asinalik.hash_satirlari(kayitlar), kosu)

    for yol in (onek_csv, hash_csv):
        satirlar = list(csv.DictReader(yol.open(encoding="utf-8")))
        assert satirlar
        for satir in satirlar:
            assert satir["kosu_komut"]
            assert satir["kosu_tarih"]
            assert satir["kosu_surum_python"]


def test_capraz_dogrulama_farki_sayiyla_bildirir(tmp_path):
    """Bilinen toplamlardan sapma, fark sayisiyla birlikte raporlanmali."""
    bos_kume(tmp_path)
    goruntu_yaz(tmp_path, "test", "test_ZRI_0001", b"s1", 4)
    kayitlar = asinalik.tum_kayitlar(tmp_path)

    uyusmazlik = asinalik.capraz_dogrula(kayitlar, {"test_hedef": 10})
    assert uyusmazlik == ["test_hedef: beklenen 10, olculen 4, fark -6"]
    assert asinalik.capraz_dogrula(kayitlar, {"test_hedef": 4}) == []
