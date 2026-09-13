"""Demo verisi uretimi -- tek yerde.

NEDEN VAR: Projeyi ilk kez acan biri (juri, isveren, yeni gelistirici) sistemi
gorebilmek icin elle gorev acmak, goruntu yuklemek, tarama baslatmak ve
inceleme girmek zorunda kalmasin. Buradaki fonksiyonlar o zinciri tek komuttan
kurulabilir hale getirir.

NE URETMEZ: Gercek GPS. Elimizdeki veri kumesinin hicbir goruntusunde EXIF GPS
yok (Hafta 5 taramasi: 1579 goruntu, 0 koordinat). Burada uretilen koordinatlar
sabit tohumlu SENTETIK degerlerdir; hicbir goruntuyle iliskileri yoktur ve her
kayit `location_source = demo` ile saklanir, arayuz de bu alana bakip kalici
bir uyari gosterir.

Iki komut bu modulu paylasir:
  - demo_konum_uret : yalnizca harita katmanini dogrulayan konum verisi
                      (Hafta 6'dan beri var, olcum kayitlari bu ada atif yapar)
  - demo_kur        : uctan uca tanitim akisi (kullanici, gorev, kare, tarama,
                      inceleme, bulgu, denetim kaydi)
"""
import math
import random

from django.contrib.gis.geos import Point

from .models import Finding

#: Hafta 6'da harita dogrulamasi icin acilan gorev. Adi olcum kayitlarinda
#: gectigi icin DEGISTIRILMEZ.
KONUM_GOREV_ADI = "DEMO — sentetik konumlar (gerçek GPS değildir)"

#: Uctan uca tanitim gorevi (demo_kur). Ad her iki modda da AYNI kalir --
#: idempotanslik bu ada bakar. Karelerin gercek mi uretilmis mi oldugu gorev
#: aciklamasinda yazar; konumlar HER IKI MODDA DA sentetiktir, bu yuzden uyari
#: adin icinde duruyor.
TANITIM_GOREV_ADI = "DEMO — Gözcü tanıtım görevi (konumlar sentetiktir)"

#: Sabit tohum: komut iki kez calistirildiginda ayni noktalar uretilir,
#: boylece ekran goruntuleri ve testler tekrarlanabilir olur.
TOHUM = 20260913

#: Taban nokta. Gercek bir olay yeri DEGILDIR; yalnizca haritanin bir yere
#: odaklanabilmesi icin secilmis bir baslangic koordinatidir.
VARSAYILAN_ENLEM = 43.5081
VARSAYILAN_BOYLAM = 16.4402

SENTETIK_NOT = "Sentetik konum; gerçek bir bulgu değildir."


def _metreden_dereceye(taban_enlem, dx_metre, dy_metre):
    """Taban noktaya gore metre cinsinden sapmayi dereceye cevirir.

    Boylamda bir derecenin metre karsiligi enleme gore daralir; bu yuzden
    kosinusle olceklenir."""
    enlem_sapmasi = dy_metre / 111320.0
    boylam_metre_derece = 111320.0 * max(0.1, abs(math.cos(math.radians(taban_enlem))))
    return enlem_sapmasi, dx_metre / boylam_metre_derece


def konum_bulgulari(gorev, kullanici, taban_enlem=VARSAYILAN_ENLEM,
                    taban_boylam=VARSAYILAN_BOYLAM):
    """Haritanin kume, tekil marker ve "konum yok" durumlarini birlikte
    gosterebilmesi icin uc kume + uzakta tek nokta + konumsuz kayit uretir.

    Kayitlar VERITABANINA YAZILMAZ; cagiran taraf bulk_create eder."""
    uretec = random.Random(TOHUM)
    kume_merkezleri = [(0, 0), (0, 900), (700, 400)]
    kayitlar = []

    for kume_sirasi, (dx, dy) in enumerate(kume_merkezleri, start=1):
        for uye in range(3):
            d_enlem, d_boylam = _metreden_dereceye(
                taban_enlem, dx + uretec.uniform(-20, 20), dy + uretec.uniform(-20, 20)
            )
            kayitlar.append(Finding(
                mission=gorev,
                title=f"Demo aday {kume_sirasi}-{uye + 1}",
                note=SENTETIK_NOT,
                location=Point(taban_boylam + d_boylam, taban_enlem + d_enlem, srid=4326),
                location_source=Finding.LocationSource.DEMO,
                location_note="Komutla üretilmiş demo koordinatı.",
                status=Finding.Status.CANDIDATE,
                created_by=kullanici,
            ))

    # Kumelerden uzakta tek nokta: kumelenmeyen bulgu de gorunsun.
    d_enlem, d_boylam = _metreden_dereceye(taban_enlem, 4000, 2500)
    kayitlar.append(Finding(
        mission=gorev,
        title="Demo aday — tekil",
        note=SENTETIK_NOT,
        location=Point(taban_boylam + d_boylam, taban_enlem + d_enlem, srid=4326),
        location_source=Finding.LocationSource.DEMO,
        location_note="Komutla üretilmiş demo koordinatı.",
        created_by=kullanici,
    ))

    # Konumsuz kayit: arayuzun "konum yok" durumunu da gosterebilmesi icin.
    kayitlar.append(Finding(
        mission=gorev,
        title="Konumsuz aday",
        note="Bu kaydın konumu yok; harita üzerinde gösterilmez.",
        location=None,
        location_source=Finding.LocationSource.NONE,
        created_by=kullanici,
    ))
    return kayitlar
