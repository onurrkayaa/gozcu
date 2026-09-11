"""Saf fonksiyon testleri. Veritabani YOK, Django ayari YOK -- milisaniyeler."""
import pytest

from core.tiling import iou, karodan_global_koordinata, karolari_hesapla, nms


def test_4000x3000_512_karo_02_ortusme_tam_80_karo():
    karolar = karolari_hesapla(4000, 3000, 512, 0.2)
    assert len(karolar) == 80
    # 10 sutun x 8 satir
    assert len({k[1] for k in karolar}) == 10
    assert len({k[0] for k in karolar}) == 8


def test_hicbir_karo_goruntu_sinirini_asmiyor():
    karolar = karolari_hesapla(4000, 3000, 512, 0.2)
    for _, _, x1, y1, x2, y2 in karolar:
        assert x1 >= 0 and y1 >= 0
        assert x2 <= 4000 and y2 <= 3000
        assert x2 > x1 and y2 > y1


def test_karolar_tum_pikselleri_kapsiyor_bosluk_yok():
    """Her eksende karo araliklarinin birlesimi kenari eksiksiz ortmeli."""
    karolar = karolari_hesapla(4000, 3000, 512, 0.2)

    def bosluk_var_mi(araliklar, kenar):
        ulasilan = 0
        for baslangic, bitis in sorted(araliklar):
            if baslangic > ulasilan:
                return True  # arada delik var
            ulasilan = max(ulasilan, bitis)
        return ulasilan < kenar

    x_araliklari = {(k[2], k[4]) for k in karolar}
    y_araliklari = {(k[3], k[5]) for k in karolar}
    assert not bosluk_var_mi(x_araliklari, 4000)
    assert not bosluk_var_mi(y_araliklari, 3000)


def test_karo_goruntuden_buyukse_tek_karo_doner():
    karolar = karolari_hesapla(300, 200, 512, 0.2)
    assert karolar == [(0, 0, 0, 0, 300, 200)]


def test_son_karo_kirpilmaz_iceri_kaydirilir():
    """4000 genislikte son sutun 512 genis kalmali, kirpilmis olmamali."""
    karolar = karolari_hesapla(4000, 3000, 512, 0.2)
    son_sutun = max(k[1] for k in karolar)
    son = next(k for k in karolar if k[1] == son_sutun)
    assert son[4] - son[2] == 512
    assert son[4] == 4000


def test_iou_ayni_kutu_bir():
    assert iou((10, 10, 50, 50), (10, 10, 50, 50)) == pytest.approx(1.0)


def test_iou_ayrik_kutular_sifir():
    assert iou((0, 0, 10, 10), (100, 100, 120, 120)) == 0.0
    # Yalnizca kenardan degiyorsa da kesisim alani sifirdir.
    assert iou((0, 0, 10, 10), (10, 0, 20, 10)) == 0.0


def test_iou_bilinen_ornek_elle_hesaplanmis():
    # A = (0,0,10,10) alan 100 ; B = (5,5,15,15) alan 100
    # kesisim = (5..10) x (5..10) = 5*5 = 25
    # birlesim = 100 + 100 - 25 = 175 ; IoU = 25/175 = 0.142857...
    assert iou((0, 0, 10, 10), (5, 5, 15, 15)) == pytest.approx(25 / 175)


def test_nms_ortusen_ikiliden_yuksek_skorlu_kaliyor():
    dusuk = (0, 0, 10, 10, 0.30)
    yuksek = (1, 1, 11, 11, 0.90)
    sonuc = nms([dusuk, yuksek], iou_esigi=0.5)
    assert sonuc == [yuksek]


def test_nms_ayrik_kutularin_ikisini_de_tutuyor():
    a = (0, 0, 10, 10, 0.30)
    b = (100, 100, 110, 110, 0.90)
    sonuc = nms([a, b], iou_esigi=0.5)
    assert sorted(sonuc, key=lambda k: k[0]) == [a, b]


def test_nms_skora_gore_azalan_donuyor():
    kutular = [
        (0, 0, 10, 10, 0.10),
        (100, 100, 110, 110, 0.90),
        (200, 200, 210, 210, 0.50),
    ]
    skorlar = [k[4] for k in nms(kutular, iou_esigi=0.5)]
    assert skorlar == sorted(skorlar, reverse=True)


def test_nms_fazladan_alanlari_koruyor():
    """nms ilk bes ogeyi kullanir, karo indeksleri dokunulmadan gecmeli."""
    kutu = (0, 0, 10, 10, 0.9, 3, 7)
    assert nms([kutu], iou_esigi=0.5) == [kutu]


def test_karodan_global_koordinata_bilinen_ornek():
    # Karo (2, 3) -> x1=1230, y1=820 varsayalim; karo icindeki (10, 20, 60, 80)
    # kutusu global duzlemde (1240, 840, 1290, 900) olmali.
    assert karodan_global_koordinata((10, 20, 60, 80), 1230, 820) == (
        1240,
        840,
        1290,
        900,
    )


def test_karodan_global_koordinata_sifir_ofset_degistirmez():
    assert karodan_global_koordinata((1, 2, 3, 4), 0, 0) == (1, 2, 3, 4)


def test_gecersiz_ortusme_orani_hata_veriyor():
    with pytest.raises(ValueError):
        karolari_hesapla(100, 100, 32, 1.0)
    with pytest.raises(ValueError):
        karolari_hesapla(100, 100, 0, 0.2)
