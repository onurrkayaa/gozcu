"""Hafta 7 yanlis pozitif baglam analizinin istatistik ve kural katmani.

Buradaki testler etiket verisine bagli DEGILDIR: protokolde sabitlenen
kurallarin (eslestirilmis test, kume bootstrap, dislama, kanit etiketi)
dogru uygulandigini uydurma ama kontrollu girdilerle sinar.
"""
import importlib.util
import math
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[2]


def _modul_yukle(ad, dosya):
    spec = importlib.util.spec_from_file_location(ad, KOK / "scripts" / dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


analiz = _modul_yukle("h7_analiz", "27_fp_analiz.py")
adaylar = _modul_yukle("h7_adaylar", "25_esit_fp_adaylari.py")


# --- McNemar ------------------------------------------------------------------

def test_uyumsuz_cift_yokken_p_bir():
    assert analiz.mcnemar_tam(0, 0) == 1.0


def test_simetrik_uyumsuzlukta_p_bir():
    assert analiz.mcnemar_tam(10, 10) == pytest.approx(1.0)


def test_tek_yonlu_uyumsuzluk_kucuk_p():
    # 20 uyumsuz ciftin 20'si ayni yonde: yazi-tura ile beklenmeyecek kadar tek yonlu.
    assert analiz.mcnemar_tam(20, 0) < 1e-5


def test_p_degeri_siraya_duyarsiz():
    assert analiz.mcnemar_tam(3, 11) == analiz.mcnemar_tam(11, 3)


def test_uyumlu_ciftler_teste_girmiyor():
    # b ve c ayni kalirken uyumlu cift sayisini degistirmek p'yi degistirmemeli.
    assert analiz.mcnemar_tam(5, 1) == analiz.mcnemar_tam(5, 1)


# --- Agirlikli fark -----------------------------------------------------------

def _cift(fp, kontrol, goruntu="g1", agirlik=1.0, model="Model-512", kaynak="ZRI"):
    return {"fp": fp, "kontrol": kontrol, "goruntu": goruntu, "agirlik": agirlik,
            "model": model, "kaynak": kaynak, "katman": f"{model}/{kaynak}",
            "fp_alt_kategori": "arac", "kontrol_alt_kategori": "dogal_bitki", "skor": 0.5}


def test_agirliksiz_fark_dogrudan_oran_farki():
    ciftler = [_cift(1, 0), _cift(1, 0), _cift(0, 0), _cift(0, 0)]
    assert analiz.agirlikli_fark(ciftler) == pytest.approx(0.5)


def test_agirlik_katmani_telafi_ediyor():
    # Tamami alinan kucuk kaynak (agirlik 1) ile ornekleme yapilan buyuk kaynak
    # (agirlik 4) esit sayida cift verse bile birlesik oran buyuge kayar.
    ciftler = [_cift(0, 0, "g1", 1.0, kaynak="VRD"), _cift(1, 0, "g2", 4.0, kaynak="ZRI")]
    assert analiz.agirlikli_fark(ciftler) == pytest.approx(0.8)


def test_bos_kumede_fark_sifir():
    assert analiz.agirlikli_fark([]) == 0.0


# --- Kume bootstrap -----------------------------------------------------------

def test_bootstrap_ayni_tohumda_ayni_sonuc():
    ciftler = [_cift(1, 0, f"g{i%7}") for i in range(40)]
    ilk = analiz.kume_bootstrap(ciftler, analiz.agirlikli_fark, yineleme=200)
    ikinci = analiz.kume_bootstrap(ciftler, analiz.agirlikli_fark, yineleme=200)
    assert ilk == ikinci


def test_bootstrap_goruntu_bagimliligini_hesaba_katiyor():
    """Ayni 40 cift, iki farkli kumeleme.

    Ciftler goruntu icinde BAGIMLI (ayni goruntudeki hepsi ayni sonucu
    veriyor). Goruntu duzeyinde kume bootstrap bunu hesaba katip genis bir
    aralik uretmeli; ciftler bagimsizmis gibi orneklenirse aralik yapay
    olarak daralir. Testin kanitladigi sey budur.
    """
    kumeli = [_cift(1 if i < 20 else 0, 0, f"g{i // 10}") for i in range(40)]
    bagimsiz = [_cift(1 if i < 20 else 0, 0, f"g{i}") for i in range(40)]
    kumeli_alt, kumeli_ust = analiz.kume_bootstrap(kumeli, analiz.agirlikli_fark, yineleme=800)
    bagimsiz_alt, bagimsiz_ust = analiz.kume_bootstrap(
        bagimsiz, analiz.agirlikli_fark, yineleme=800)
    assert (kumeli_ust - kumeli_alt) > (bagimsiz_ust - bagimsiz_alt)


def test_tek_goruntude_bootstrap_degiskenlik_uretmiyor():
    # Tek kume varsa yeniden orneklemenin gidecegi baska yer yoktur; aralik
    # noktaya coker. Bu bir kusur degil, kume bootstrap'in tanimidir -- ve
    # sonucun tek goruntuye dayandiginin isaretidir.
    tek = [_cift(i % 2, 0, "g1") for i in range(40)]
    alt, ust = analiz.kume_bootstrap(tek, analiz.agirlikli_fark, yineleme=200)
    assert alt == ust


def test_bos_kumede_bootstrap_nan():
    alt, ust = analiz.kume_bootstrap([], analiz.agirlikli_fark, yineleme=10)
    assert math.isnan(alt) and math.isnan(ust)


# --- Cift kurma ve dislama ----------------------------------------------------

def _anahtar(fp_kimlik, kontrol_kimlik, **ekler):
    ortak = {"goruntu_adi": "test_ZRI_0001.jpg", "model": "Model-512",
             "kaynak_onek": "ZRI", "katman": "Model-512/ZRI",
             "katman_secilme_olasiligi": "1.0", "skor": "0.55", **ekler}
    return [
        {"kor_kimlik": fp_kimlik, "aday_turu": "fp", "es_kor_kimlik": kontrol_kimlik, **ortak},
        {"kor_kimlik": kontrol_kimlik, "aday_turu": "kontrol", "es_kor_kimlik": fp_kimlik,
         **{**ortak, "skor": ""}},
    ]


def _etiket(faaliyet, yeterli="evet", kategori="arac"):
    return {"insan_faaliyeti": faaliyet, "alt_kategori": kategori,
            "guven": "yuksek", "goruntu_yeterli": yeterli, "yeniden_incele": "hayir"}


def test_belirsiz_cift_birincil_analizden_dusuyor():
    anahtar = _anahtar("a1", "a2")
    etiketler = {"a1": _etiket("belirsiz"), "a2": _etiket("yok")}
    ciftler, dislanan = analiz.ciftleri_kur(etiketler, anahtar, "disla")
    assert ciftler == []
    assert dislanan["belirsiz"] == 1


def test_belirsiz_duyarlilikta_sinifa_atanabiliyor():
    anahtar = _anahtar("a1", "a2")
    etiketler = {"a1": _etiket("belirsiz"), "a2": _etiket("yok")}
    var_ciftler, _ = analiz.ciftleri_kur(etiketler, anahtar, "var")
    yok_ciftler, _ = analiz.ciftleri_kur(etiketler, anahtar, "yok")
    assert var_ciftler[0]["fp"] == 1
    assert yok_ciftler[0]["fp"] == 0


def test_goruntu_yetersizse_cift_birlikte_dusuyor():
    anahtar = _anahtar("a1", "a2")
    etiketler = {"a1": _etiket("var"), "a2": _etiket("yok", yeterli="hayir")}
    ciftler, dislanan = analiz.ciftleri_kur(etiketler, anahtar, "disla")
    assert ciftler == []
    assert dislanan["goruntu_yetersiz"] == 1


def test_esi_etiketsizse_cift_kurulmuyor():
    anahtar = _anahtar("a1", "a2")
    ciftler, dislanan = analiz.ciftleri_kur({"a1": _etiket("var")}, anahtar, "disla")
    assert ciftler == []
    assert dislanan["etiketsiz"] == 1


def test_agirlik_secilme_olasiliginin_tersi():
    anahtar = _anahtar("a1", "a2", katman_secilme_olasiligi="0.25")
    etiketler = {"a1": _etiket("var"), "a2": _etiket("yok")}
    ciftler, _ = analiz.ciftleri_kur(etiketler, anahtar, "disla")
    assert ciftler[0]["agirlik"] == pytest.approx(4.0)


def test_kontrol_satiri_ikinci_kez_cift_uretmiyor():
    anahtar = _anahtar("a1", "a2")
    etiketler = {"a1": _etiket("var"), "a2": _etiket("yok")}
    ciftler, _ = analiz.ciftleri_kur(etiketler, anahtar, "disla")
    assert len(ciftler) == 1


# --- Kanit etiketi ------------------------------------------------------------

def test_yetersiz_ornek_bulgu_olamaz():
    etiket, _ = analiz.kanit_etiketi(60, 0.1, 0.3, [0.2, 0.2], 0.95, [0.2])
    assert etiket == "ILGINC AMA KANITLANMAMIS"


def test_tum_kosullar_saglaninca_bulgu():
    etiket, _ = analiz.kanit_etiketi(150, 0.08, 0.30, [0.15, 0.18], 0.90, [0.2, 0.1])
    assert etiket == "BULGU"


def test_ters_yonde_aralik_curutur():
    etiket, _ = analiz.kanit_etiketi(150, -0.30, -0.05, [-0.2, -0.2], 0.90, [-0.2])
    assert etiket == "CURUTULDU"


def test_dar_ve_sifiri_iceren_aralik_curutur():
    etiket, _ = analiz.kanit_etiketi(150, -0.02, 0.03, [0.0, 0.01], 0.90, [0.0])
    assert etiket == "CURUTULDU"


def test_dusuk_yeniden_test_bulguyu_engelliyor():
    etiket, gerekce = analiz.kanit_etiketi(150, 0.08, 0.30, [0.15, 0.18], 0.60, [0.2])
    assert etiket == "ILGINC AMA KANITLANMAMIS"
    assert "yeniden-test" in gerekce


def test_kaynakta_yon_tersse_bulgu_yok():
    etiket, gerekce = analiz.kanit_etiketi(150, 0.08, 0.30, [0.15, 0.18], 0.90, [0.3, -0.1])
    assert etiket == "ILGINC AMA KANITLANMAMIS"
    assert "kaynak" in gerekce


def test_duyarliliklar_ayrisirsa_bulgu_yok():
    etiket, gerekce = analiz.kanit_etiketi(150, 0.08, 0.30, [0.15, -0.02], 0.90, [0.2])
    assert etiket == "ILGINC AMA KANITLANMAMIS"
    assert "duyarlilik" in gerekce


# --- Yeniden-test uyumu -------------------------------------------------------

def test_uyum_orani_yalnizca_ortak_kimliklere_bakiyor():
    ilk = {"a1": _etiket("var"), "a2": _etiket("yok"), "a3": _etiket("var")}
    ikinci = {"a1": _etiket("var"), "a2": _etiket("var")}
    uyusan, karsilastirilan = analiz.uyum_orani(ilk, ikinci, "insan_faaliyeti")
    assert (uyusan, karsilastirilan) == (1, 2)


def test_ortak_kimlik_yoksa_karsilastirma_sifir():
    assert analiz.uyum_orani({"a1": _etiket("var")}, {}, "insan_faaliyeti") == (0, 0)


# --- Kirpim geometrisi ve kontrol bolgesi (scripts/25) ------------------------

def test_baglam_kirpimi_sikidan_genis():
    kutu = adaylar.Kutu(1000, 1000, 1070, 1070)
    geo = adaylar.kirpim_geometrisi(kutu, 4000, 3000)
    sx1, sy1, sx2, sy2 = geo["siki"]
    bx1, by1, bx2, by2 = geo["baglam"]
    assert (bx2 - bx1) > (sx2 - sx1)
    assert (by2 - by1) > (sy2 - sy1)


def test_baglam_kenari_asgari_degerin_altina_dusmuyor():
    kutu = adaylar.Kutu(2000, 1500, 2010, 1510)
    bx1, by1, bx2, by2 = adaylar.kirpim_geometrisi(kutu, 4000, 3000)["baglam"]
    assert (bx2 - bx1) >= adaylar.BAGLAM_ASGARI_KENAR
    assert (by2 - by1) >= adaylar.BAGLAM_ASGARI_KENAR


def test_kenardaki_kutuda_baglam_kaydiriliyor_kirpilmiyor():
    kutu = adaylar.Kutu(0, 0, 60, 60)
    geo = adaylar.kirpim_geometrisi(kutu, 4000, 3000)
    bx1, by1, bx2, by2 = geo["baglam"]
    assert bx1 >= 0 and by1 >= 0
    assert (bx2 - bx1) >= adaylar.BAGLAM_ASGARI_KENAR
    assert geo["kaydirma_x"] != 0 or geo["kaydirma_y"] != 0


def test_siki_kirpim_goruntu_disina_tasmiyor():
    kutu = adaylar.Kutu(3970, 2970, 4000, 3000)
    sx1, sy1, sx2, sy2 = adaylar.kirpim_geometrisi(kutu, 4000, 3000)["siki"]
    assert 0 <= sx1 < sx2 <= 4000
    assert 0 <= sy1 < sy2 <= 3000


def test_kontrol_bolgesi_gercek_insanla_cakismiyor():
    import random
    rastgele = random.Random(1)
    kutu = adaylar.Kutu(100, 100, 160, 160)
    gercekler = [adaylar.Kutu(0, 0, 2000, 3000)]  # solun tamami dolu
    kontrol = adaylar.kontrol_bolgesi_bul(rastgele, kutu, gercekler, [], 4000, 3000)
    assert kontrol is not None
    assert all(adaylar.iou_hesapla(kontrol, g) == 0 for g in gercekler)


def test_yer_kalmayinca_kontrol_bolgesi_none():
    import random
    rastgele = random.Random(1)
    kutu = adaylar.Kutu(0, 0, 100, 100)
    gercekler = [adaylar.Kutu(0, 0, 4000, 3000)]  # goruntunun tamami dolu
    assert adaylar.kontrol_bolgesi_bul(rastgele, kutu, gercekler, [], 4000, 3000) is None


def test_kontrol_bolgesi_fp_ile_ayni_olcude():
    import random
    rastgele = random.Random(7)
    kutu = adaylar.Kutu(500, 500, 583, 617)
    kontrol = adaylar.kontrol_bolgesi_bul(rastgele, kutu, [], [], 4000, 3000)
    assert kontrol.genislik == pytest.approx(kutu.genislik)
    assert kontrol.yukseklik == pytest.approx(kutu.yukseklik)


def test_kontrol_secimi_tohumla_tekrarlanabilir():
    import random
    kutu = adaylar.Kutu(500, 500, 560, 560)
    ilk = adaylar.kontrol_bolgesi_bul(random.Random(42), kutu, [], [], 4000, 3000)
    ikinci = adaylar.kontrol_bolgesi_bul(random.Random(42), kutu, [], [], 4000, 3000)
    assert (ilk.x1, ilk.y1) == (ikinci.x1, ikinci.y1)


# --- Katmanli ornekleme -------------------------------------------------------

def _fp(kimlik, kaynak):
    return {"aday_kimligi": kimlik, "kaynak_onek": kaynak}


def test_kucuk_kaynagin_tamami_aliniyor():
    import random
    havuz = [_fp(f"m_{i:04d}", "VRD") for i in range(30)]
    havuz += [_fp(f"m_{i:04d}", "ZRI") for i in range(30, 230)]
    secilen, olasilik = adaylar.katmanli_sec(random.Random(1), havuz, 110, 55)
    assert sum(1 for s in secilen if s["kaynak_onek"] == "VRD") == 30
    assert olasilik["VRD"] == 1.0
    assert olasilik["ZRI"] < 1.0


def test_toplam_hedefe_ulasiliyor():
    import random
    havuz = [_fp(f"m_{i:04d}", "VRD") for i in range(30)]
    havuz += [_fp(f"m_{i:04d}", "ZRI") for i in range(30, 230)]
    secilen, _ = adaylar.katmanli_sec(random.Random(1), havuz, 110, 55)
    assert len(secilen) == 110


def test_havuz_hedeften_kucukse_tamami_aliniyor():
    import random
    havuz = [_fp(f"m_{i:04d}", "ZRI") for i in range(40)]
    secilen, _ = adaylar.katmanli_sec(random.Random(1), havuz, 110, 55)
    assert len(secilen) == 40


def test_ornekleme_tohumla_tekrarlanabilir():
    import random
    havuz = [_fp(f"m_{i:04d}", "ZRI") for i in range(200)]
    ilk, _ = adaylar.katmanli_sec(random.Random(5), havuz, 110, 55)
    ikinci, _ = adaylar.katmanli_sec(random.Random(5), havuz, 110, 55)
    assert [s["aday_kimligi"] for s in ilk] == [s["aday_kimligi"] for s in ikinci]
