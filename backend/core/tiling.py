"""Karolama ve kutu geometrisi. SAF fonksiyonlar.

Bu dosya veritabanina, dosyaya veya aga DOKUNMAZ; Django bile import edilmez.
Boylece bu mantik, yavas dedektorden ve ayakta bir Postgres'ten bagimsiz olarak
milisaniyeler icinde test edilebilir.

Kutu bicimi her yerde (x1, y1, x2, y2), x2/y2 haric (yarik acik araliklar).
Karo bicimi (satir, sutun, x1, y1, x2, y2).
"""
import math


def _bir_eksende_baslangiclar(kenar, karo_boyu, adim, ortusme_px):
    """Tek bir eksendeki karo baslangic koordinatlarini uretir."""
    if karo_boyu >= kenar:
        # Karo goruntuden buyuk: iceri kaydiracak yer yok, tek karo kalir ve
        # cagiran taraf sinira kirpar.
        return [0]

    sayi = math.ceil((kenar - ortusme_px) / adim)
    sayi = max(1, sayi)

    baslangiclar = []
    for i in range(sayi):
        baslangic = i * adim
        if baslangic + karo_boyu > kenar:
            # Son karo sinirdan tasti: KIRPMIYORUZ, iceri kaydiriyoruz. Karo
            # boyu sabit kalsin ki dedektor her zaman ayni olcude girdi gorsun.
            baslangic = kenar - karo_boyu
        baslangiclar.append(baslangic)
    return baslangiclar


def karolari_hesapla(genislik, yukseklik, karo_boyu, ortusme_orani):
    """Goruntuyu ortusmeli karolara boler.

    adim      = karo_boyu - int(karo_boyu * ortusme_orani)
    karo sayisi = ceil((kenar - ortusme_px) / adim)

    Son karo goruntu sinirini tasarsa iceri kaydirilir, kirpilmaz. Karo boyu
    goruntuden buyukse tek karo doner ve goruntu sinirina kirpilir.

    (satir, sutun, x1, y1, x2, y2) uclulerinden olusan liste doner; satir sonra
    sutun sirasinda.
    """
    if genislik <= 0 or yukseklik <= 0:
        raise ValueError("Goruntu olculeri pozitif olmali.")
    if karo_boyu <= 0:
        raise ValueError("Karo boyu pozitif olmali.")
    if not 0 <= ortusme_orani < 1:
        raise ValueError("Ortusme orani [0, 1) araliginda olmali.")

    ortusme_px = int(karo_boyu * ortusme_orani)
    adim = karo_boyu - ortusme_px
    if adim <= 0:
        raise ValueError("Adim sifir veya negatif; ortusme orani cok yuksek.")

    x_baslangiclari = _bir_eksende_baslangiclar(genislik, karo_boyu, adim, ortusme_px)
    y_baslangiclari = _bir_eksende_baslangiclar(yukseklik, karo_boyu, adim, ortusme_px)

    karolar = []
    for satir, y1 in enumerate(y_baslangiclari):
        for sutun, x1 in enumerate(x_baslangiclari):
            # min() yalnizca "karo goruntuden buyuk" durumunda is yapar.
            x2 = min(x1 + karo_boyu, genislik)
            y2 = min(y1 + karo_boyu, yukseklik)
            karolar.append((satir, sutun, x1, y1, x2, y2))
    return karolar


def karodan_global_koordinata(kutu, karo_x1, karo_y1):
    """Karo duzlemindeki bir kutuyu orijinal goruntu duzlemine tasir."""
    x1, y1, x2, y2 = kutu
    return (x1 + karo_x1, y1 + karo_y1, x2 + karo_x1, y2 + karo_y1)


def iou(kutu_a, kutu_b):
    """Iki kutunun kesisim/birlesim oranini doner. Ayrik kutularda 0.0."""
    ax1, ay1, ax2, ay2 = kutu_a
    bx1, by1, bx2, by2 = kutu_b

    kesisim_genislik = min(ax2, bx2) - max(ax1, bx1)
    kesisim_yukseklik = min(ay2, by2) - max(ay1, by1)
    if kesisim_genislik <= 0 or kesisim_yukseklik <= 0:
        return 0.0
    kesisim = kesisim_genislik * kesisim_yukseklik

    alan_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    alan_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    birlesim = alan_a + alan_b - kesisim
    if birlesim <= 0:
        return 0.0
    return kesisim / birlesim


def nms(kutular, iou_esigi):
    """Acgozlu maksimum olmayani bastirma.

    kutular: (x1, y1, x2, y2, skor) besliler listesi.
    Skora gore azalan sirada gezer; secilen bir kutuyla IoU'su esigi ASAN
    kutulari eler. Girdi listesini degistirmez.
    """
    if not 0 <= iou_esigi <= 1:
        raise ValueError("IoU esigi [0, 1] araliginda olmali.")

    # Skora gore azalan; esitlikte girdi sirasi korunsun diye indeks ikincil
    # anahtar (sort kararli, bu yuzden yalnizca skora gore siralamak yeterli).
    sirali = sorted(kutular, key=lambda k: k[4], reverse=True)

    tutulanlar = []
    for aday in sirali:
        bastirildi = False
        for tutulan in tutulanlar:
            if iou(aday[:4], tutulan[:4]) > iou_esigi:
                bastirildi = True
                break
        if not bastirildi:
            tutulanlar.append(aday)
    return tutulanlar
