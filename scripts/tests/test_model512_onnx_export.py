"""17_model512_onnx_export.py icindeki kimlik, dogrulama ve CSV islevlerinin testleri.

Gercek export BURADA TEKRARLANMAZ: agirlik yuklenmez, model calistirilmaz.
Testler kucuk gecici dosyalar ve elle kurulan minik bir ONNX grafigi kullanir.
"""

import csv
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

PROJE_KOK = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIZIN = PROJE_KOK / "scripts"

# Dosya adi rakamla basladigi icin normal import edilemez; yoldan yukluyoruz.
sys.path.insert(0, str(SCRIPT_DIZIN))

_spec = importlib.util.spec_from_file_location(
    "onnx_export", SCRIPT_DIZIN / "17_model512_onnx_export.py"
)
disa_aktar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(disa_aktar)

RAPOR_KOK = PROJE_KOK / "reports"


def minik_onnx_yaz(yol: Path, opset: int = 18) -> Path:
    """Elle kurulmus, checker'dan gecen en kucuk ONNX grafigi."""
    import onnx
    from onnx import TensorProto, helper

    girdi = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 8, 8])
    cikti = helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1, 3, 8, 8])
    grafik = helper.make_graph(
        [helper.make_node("Identity", ["images"], ["output0"])], "minik", [girdi], [cikti]
    )
    model = helper.make_model(grafik, opset_imports=[helper.make_opsetid("", opset)])
    onnx.save(model, str(yol))
    return yol


def sahte_kaynak(tmp_path: Path, icerik: bytes = b"agirlik-baytlari") -> Path:
    yol = tmp_path / "model512_best.pt"
    yol.write_bytes(icerik)
    return yol


def egitim_ciktisi_kur(tmp_path: Path, icerik: bytes, imgsz: int = 512) -> Path:
    """Kaggle kosu ciktisinin kucuk bir taklidi: args.yaml + weights/best.pt."""
    kok = tmp_path / "kaggle_cikti" / "egitim" / "model512"
    (kok / "weights").mkdir(parents=True, exist_ok=True)
    (kok / "weights" / "best.pt").write_bytes(icerik)
    (kok / "args.yaml").write_text(f"imgsz: {imgsz}\nbatch: 16\n", encoding="utf-8")
    return tmp_path / "kaggle_cikti"


# --- Dosya kimligi ------------------------------------------------------------


def test_sha256_dosya_iceriginden_hesaplaniyor(tmp_path):
    """Ozet, dosya baytlarindan hesaplanmali; ad veya yol hesaba girmemeli."""
    icerik = b"model-baytlari-123"
    a = sahte_kaynak(tmp_path, icerik)
    b = tmp_path / "baska_ad.pt"
    b.write_bytes(icerik)

    beklenen = hashlib.sha256(icerik).hexdigest()
    assert disa_aktar.dosya_kimligi(a)["sha256"] == beklenen
    assert disa_aktar.dosya_kimligi(b)["sha256"] == beklenen

    b.write_bytes(icerik + b"x")
    assert disa_aktar.dosya_kimligi(b)["sha256"] != beklenen


def test_dosya_boyutu_dogru_okunuyor(tmp_path):
    """Boyut, diskteki bayt sayisina esit olmali."""
    icerik = b"a" * 4096
    yol = sahte_kaynak(tmp_path, icerik)
    assert disa_aktar.dosya_kimligi(yol)["boyut_bayt"] == 4096
    assert disa_aktar.dosya_kimligi(yol)["boyut_bayt"] == yol.stat().st_size


def test_kaynak_pt_bulunmazsa_acik_hata(tmp_path):
    """Yanlis yol verildiginde hata mesaji yolu icermeli."""
    yok = tmp_path / "olmayan_model.pt"
    with pytest.raises(FileNotFoundError) as hata:
        disa_aktar.dosya_kimligi(yok)
    assert "olmayan_model.pt" in str(hata.value)


# --- Ozgun agirlik karsilastirmasi --------------------------------------------


def test_ozgun_best_pt_ayni_ise_uyusuyor(tmp_path):
    """Ayni baytlara sahip ozgun best.pt UYUSTU vermeli."""
    icerik = b"ayni-agirlik"
    kaynak = disa_aktar.dosya_kimligi(sahte_kaynak(tmp_path, icerik))
    egitim = egitim_ciktisi_kur(tmp_path, icerik)
    sonuc = disa_aktar.ozgun_agirlikla_karsilastir(kaynak, egitim)
    assert sonuc["durum"] == "UYUSTU"
    assert sonuc["sha256"] == kaynak["sha256"]


def test_ozgun_best_pt_hashi_farkliysa_kapi_gecmiyor(tmp_path):
    """Farkli baytlar UYUSMADI vermeli; ana akis bu durumda export yapmaz."""
    kaynak = disa_aktar.dosya_kimligi(sahte_kaynak(tmp_path, b"kaynak-agirlik"))
    egitim = egitim_ciktisi_kur(tmp_path, b"baska-agirlik")
    assert disa_aktar.ozgun_agirlikla_karsilastir(kaynak, egitim)["durum"] == "UYUSMADI"


def test_args_yaml_tek_aday_olmali(tmp_path):
    """args.yaml aranarak bulunur; hic yoksa veya birden fazlaysa durulur."""
    egitim = egitim_ciktisi_kur(tmp_path, b"agirlik")
    bulunan = disa_aktar.args_yaml_bul(egitim)
    assert bulunan.name == "args.yaml"
    assert disa_aktar.args_oku(bulunan)["imgsz"] == 512

    with pytest.raises(SystemExit):
        disa_aktar.args_yaml_bul(tmp_path / "bos_klasor")

    ikinci = egitim / "ikinci" / "model512"
    ikinci.mkdir(parents=True)
    (ikinci / "args.yaml").write_text("imgsz: 320\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        disa_aktar.args_yaml_bul(egitim)


# --- Yapisal ONNX dogrulamasi -------------------------------------------------


def test_onnx_metadata_eksiksiz_okunuyor(tmp_path):
    """Opset, girdi/cikti adlari, sekilleri ve veri turleri okunabilmeli."""
    yapi = disa_aktar.onnx_yapisal_dogrula(minik_onnx_yaz(tmp_path / "minik.onnx"))
    assert yapi["checker_durumu"] == "GECTI"
    assert yapi["opset"] == 18
    assert yapi["girdi_adlari"] == "images"
    assert yapi["girdi_sekilleri"] == "images:1x3x8x8"
    assert yapi["girdi_veri_turleri"] == "images:FLOAT"
    assert yapi["cikti_adlari"] == "output0"
    assert yapi["cikti_sekilleri"] == "output0:1x3x8x8"
    assert yapi["cikti_veri_turleri"] == "output0:FLOAT"


def test_bozuk_onnx_dosyasinda_kapi_gecmiyor(tmp_path):
    """Acilamayan dosya sessizce gecilmemeli."""
    bozuk = tmp_path / "bozuk.onnx"
    bozuk.write_bytes(b"bu bir onnx grafigi degil")
    with pytest.raises(Exception):
        disa_aktar.onnx_yapisal_dogrula(bozuk)


def test_bos_veya_eksik_onnx_dosyasinda_kapi_gecmiyor(tmp_path):
    """Bos dosya ve olmayan dosya ayri ayri hata vermeli."""
    bos = tmp_path / "bos.onnx"
    bos.write_bytes(b"")
    with pytest.raises(ValueError):
        disa_aktar.onnx_yapisal_dogrula(bos)
    with pytest.raises(FileNotFoundError):
        disa_aktar.onnx_yapisal_dogrula(tmp_path / "olmayan.onnx")


def test_checker_basarisizsa_hata_yukseliyor(tmp_path):
    """onnx.checker'dan gecemeyen grafik hata vermeli."""
    import onnx
    from onnx import TensorProto, helper

    girdi = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 8, 8])
    cikti = helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1, 3, 8, 8])
    # Tanimsiz operator: checker bunu kabul etmemeli.
    grafik = helper.make_graph(
        [helper.make_node("BoyleBirOpYok", ["images"], ["output0"])],
        "hatali", [girdi], [cikti],
    )
    model = helper.make_model(grafik, opset_imports=[helper.make_opsetid("", 18)])
    yol = tmp_path / "hatali.onnx"
    onnx.save(model, str(yol))

    with pytest.raises(onnx.checker.ValidationError):
        disa_aktar.onnx_yapisal_dogrula(yol)


# --- CSV ----------------------------------------------------------------------


def olcum_kur(tmp_path: Path) -> dict:
    """Testler icin tek bir olcum satiri uretir."""
    icerik = b"agirlik"
    kaynak = disa_aktar.dosya_kimligi(sahte_kaynak(tmp_path, icerik))
    egitim = egitim_ciktisi_kur(tmp_path, icerik)
    onnx_yolu = minik_onnx_yaz(tmp_path / "minik.onnx")
    return disa_aktar.olcum_satiri(
        kaynak,
        "0:human",
        disa_aktar.args_yaml_bul(egitim),
        disa_aktar.ozgun_agirlikla_karsilastir(kaynak, egitim),
        disa_aktar.dosya_kimligi(onnx_yolu),
        disa_aktar.onnx_yapisal_dogrula(onnx_yolu),
        512,
        18,
    )


def test_csvde_zorunlu_alanlar_ve_metadata_var(tmp_path):
    """Kimlik, export ayarlari ve kosu metadata'si CSV'de bulunmali."""
    kosu = disa_aktar.kosu_bilgisi(
        kaynak_script="scripts/17_model512_onnx_export.py",
        surum_onnx="1.22.0", surum_onnxruntime="1.30.0", surum_onnxslim="0.1.96",
    )
    yol = disa_aktar.csv_yaz(tmp_path / "onnx_bilgisi.csv", [olcum_kur(tmp_path)], kosu)

    satir = list(csv.DictReader(yol.open(encoding="utf-8")))[0]
    for alan in (
        "kaynak_pt", "kaynak_pt_boyut_bayt", "kaynak_pt_sha256", "kaynak_sinif_adlari",
        "args_yaml", "onnx_dosyasi", "onnx_boyut_bayt", "onnx_sha256", "onnx_opset",
        "onnx_girdi_adlari", "onnx_girdi_sekilleri", "onnx_girdi_veri_turleri",
        "onnx_cikti_adlari", "onnx_cikti_sekilleri", "onnx_cikti_veri_turleri",
        "export_imgsz", "export_batch", "export_dynamic", "export_simplify",
        "export_half", "export_device", "onnx_checker_durumu",
        "kosu_komut", "kosu_tarih", "kosu_surum_python", "kosu_surum_ultralytics",
        "kosu_surum_torch", "kosu_surum_onnx", "kosu_surum_onnxruntime",
        "kosu_surum_onnxslim", "kosu_kaynak_script",
    ):
        assert satir[alan] != "", f"bos alan: {alan}"


def test_girdi_cikti_bilgisi_kaybolmadan_csvye_yaziliyor(tmp_path):
    """Grafikten okunan girdi/cikti metadata'si CSV'ye birebir gecmeli."""
    satir = olcum_kur(tmp_path)
    yol = disa_aktar.csv_yaz(tmp_path / "bilgi.csv", [satir], disa_aktar.kosu_bilgisi())
    okunan = list(csv.DictReader(yol.open(encoding="utf-8")))[0]
    for alan in (
        "onnx_girdi_adlari", "onnx_girdi_sekilleri", "onnx_girdi_veri_turleri",
        "onnx_cikti_adlari", "onnx_cikti_sekilleri", "onnx_cikti_veri_turleri",
        "onnx_opset",
    ):
        assert okunan[alan] == str(satir[alan])
    assert okunan["onnx_girdi_sekilleri"] == "images:1x3x8x8"


def test_ayni_bilgi_ayni_sirali_csv_uretiyor(tmp_path):
    """Ayni satir ve ayni kosu bilgisi, ayni basliklari ayni sirada vermeli."""
    satir = olcum_kur(tmp_path)
    kosu = disa_aktar.kosu_bilgisi(kaynak_script="scripts/17_model512_onnx_export.py")
    birinci = disa_aktar.csv_yaz(tmp_path / "bir.csv", [satir], kosu)
    ikinci = disa_aktar.csv_yaz(tmp_path / "iki.csv", [satir], kosu)
    assert birinci.read_text(encoding="utf-8") == ikinci.read_text(encoding="utf-8")


def test_eski_csv_ve_rapor_dosyalari_degismiyor(tmp_path):
    """Yardimci islevler depodaki mevcut olcum ve rapor dosyalarina dokunmamali."""
    izlenen = sorted(RAPOR_KOK.glob("*.csv")) + sorted((PROJE_KOK / "rapor").glob("*.md"))
    onceki = {y: hashlib.sha256(y.read_bytes()).hexdigest() for y in izlenen}

    disa_aktar.csv_yaz(tmp_path / "yeni.csv", [olcum_kur(tmp_path)], disa_aktar.kosu_bilgisi())

    assert {y: hashlib.sha256(y.read_bytes()).hexdigest() for y in izlenen} == onceki
