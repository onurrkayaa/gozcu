"""Union-Find kumelemesi: mesafe, gecislilik, determinizm ve sinirlar.

Mesafeler gercek PostGIS uzerinden olculur. Test noktalari metre cinsinden
uretilir; asagidaki yardimci YALNIZCA test verisi kurmak icindir, kumeleme
kodu bu cevrimi kullanmaz.
"""
import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from core.kumeleme import BirlestirBul, gorevi_kumele, kume_ozeti
from core.models import Finding, Mission

pytestmark = pytest.mark.django_db

TABAN_ENLEM, TABAN_BOYLAM = 0.0, 30.0
ESIK = 50.0


def _nokta(metre_dogu):
    """Ekvatorda taban noktasindan belirtilen metre kadar doguda bir nokta."""
    return Point(TABAN_BOYLAM + metre_dogu / 111320.0, TABAN_ENLEM, srid=4326)


def _bulgu(mission, kullanici, metre=None, kaynak="manual", baslik=""):
    return Finding.objects.create(
        mission=mission,
        title=baslik,
        location=None if metre is None else _nokta(metre),
        location_source="none" if metre is None else kaynak,
        created_by=kullanici,
    )


def _uyelikler(mission):
    """{kume_anahtari: [baslik, ...]} -- kume icerigi okunabilir bicimde."""
    gruplar = {}
    for bulgu in Finding.objects.filter(mission=mission).order_by("id"):
        anahtar = (
            "kumesiz" if bulgu.cluster_id is None
            else f"{bulgu.cluster_key}#{bulgu.cluster_id}"
        )
        gruplar.setdefault(anahtar, []).append(bulgu.title)
    return {k: sorted(v) for k, v in gruplar.items()}


# --- Union-Find veri yapisi ----------------------------------------------


def test_birlestir_bul_gecisli_baglar():
    bb = BirlestirBul([1, 2, 3, 4])
    bb.birlestir(1, 2)
    bb.birlestir(2, 3)

    gruplar = bb.gruplar()
    assert len(gruplar) == 2
    assert [1, 2, 3] in gruplar.values()


def test_birlestir_bul_ayni_kokte_ikinci_birlesim_etkisiz():
    bb = BirlestirBul([1, 2])
    assert bb.birlestir(1, 2) is True
    assert bb.birlestir(1, 2) is False


def test_birlestir_bul_birlesim_sirasindan_bagimsiz():
    ileri = BirlestirBul([1, 2, 3])
    ileri.birlestir(1, 2); ileri.birlestir(2, 3)

    geri = BirlestirBul([1, 2, 3])
    geri.birlestir(3, 2); geri.birlestir(2, 1)

    assert sorted(map(sorted, ileri.gruplar().values())) == \
           sorted(map(sorted, geri.gruplar().values()))


# --- Mesafe senaryolari ---------------------------------------------------


def test_tek_nokta_tek_kume(rollu_gorev, owner_user):
    _bulgu(rollu_gorev, owner_user, 0, baslik="A")
    sonuc = gorevi_kumele(rollu_gorev, esik_metre=ESIK)
    assert sonuc["kume_sayisi"] == 1


def test_yakin_iki_nokta_birlesiyor(rollu_gorev, owner_user):
    _bulgu(rollu_gorev, owner_user, 0, baslik="A")
    _bulgu(rollu_gorev, owner_user, 10, baslik="B")

    sonuc = gorevi_kumele(rollu_gorev, esik_metre=ESIK)
    assert sonuc["kume_sayisi"] == 1
    assert _uyelikler(rollu_gorev) == {"gercek#1": ["A", "B"]}


def test_uzak_iki_nokta_ayriliyor(rollu_gorev, owner_user):
    _bulgu(rollu_gorev, owner_user, 0, baslik="A")
    _bulgu(rollu_gorev, owner_user, 500, baslik="B")

    sonuc = gorevi_kumele(rollu_gorev, esik_metre=ESIK)
    assert sonuc["kume_sayisi"] == 2


def test_gecislilik_esik_disi_ciftleri_de_birlestiriyor(rollu_gorev, owner_user):
    """A-B 40 m, B-C 40 m, A-C 80 m. Esik 50 m ama ucu de ayni kumede.

    Bu KASITLI bir davranis: bagli bilesen tanimi boyle. Eger bu test
    bozulursa, kumelemenin gecisliligi kaybolmus demektir.
    """
    _bulgu(rollu_gorev, owner_user, 0, baslik="A")
    _bulgu(rollu_gorev, owner_user, 40, baslik="B")
    _bulgu(rollu_gorev, owner_user, 80, baslik="C")

    sonuc = gorevi_kumele(rollu_gorev, esik_metre=ESIK)
    assert sonuc["kume_sayisi"] == 1
    assert _uyelikler(rollu_gorev) == {"gercek#1": ["A", "B", "C"]}


def test_ayni_koordinat_tek_kume(rollu_gorev, owner_user):
    for ad in "ABC":
        _bulgu(rollu_gorev, owner_user, 0, baslik=ad)
    assert gorevi_kumele(rollu_gorev, esik_metre=ESIK)["kume_sayisi"] == 1


def test_esik_sinirinin_iki_yani(rollu_gorev, owner_user):
    _bulgu(rollu_gorev, owner_user, 0, baslik="A")
    _bulgu(rollu_gorev, owner_user, 49, baslik="B")
    assert gorevi_kumele(rollu_gorev, esik_metre=ESIK)["kume_sayisi"] == 1

    Finding.objects.filter(mission=rollu_gorev, title="B").update(location=_nokta(51))
    assert gorevi_kumele(rollu_gorev, esik_metre=ESIK)["kume_sayisi"] == 2


def test_mesafe_metre_cinsinden_derece_degil(rollu_gorev, owner_user):
    """Derece Oklid mesafesi kullanilsaydi 0,001 derece (~111 m) 'yakin'
    gorunurdu; metre olculdugu icin 50 m esiginin disinda kaliyor."""
    _bulgu(rollu_gorev, owner_user, 0, baslik="A")
    Finding.objects.create(
        mission=rollu_gorev, title="B",
        location=Point(TABAN_BOYLAM + 0.001, TABAN_ENLEM, srid=4326),
        location_source="manual", created_by=owner_user,
    )
    assert gorevi_kumele(rollu_gorev, esik_metre=ESIK)["kume_sayisi"] == 2


# --- Gruplar ve sinirlar --------------------------------------------------


def test_demo_ve_gercek_ayri_kumeleniyor(rollu_gorev, owner_user):
    _bulgu(rollu_gorev, owner_user, 0, kaynak="manual", baslik="A")
    _bulgu(rollu_gorev, owner_user, 5, kaynak="demo", baslik="B")

    sonuc = gorevi_kumele(rollu_gorev, esik_metre=ESIK)
    assert sonuc["kume_sayisi"] == 2
    assert _uyelikler(rollu_gorev) == {"gercek#1": ["A"], "demo#1": ["B"]}


def test_konumsuz_bulgu_kumelenmiyor(rollu_gorev, owner_user):
    _bulgu(rollu_gorev, owner_user, 0, baslik="A")
    _bulgu(rollu_gorev, owner_user, None, baslik="B")

    sonuc = gorevi_kumele(rollu_gorev, esik_metre=ESIK)
    assert sonuc["kumelenen_bulgu"] == 1
    assert sonuc["konumsuz_bulgu"] == 1
    assert _uyelikler(rollu_gorev)["kumesiz"] == ["B"]


def test_gorev_sinirlari_karismiyor(rollu_gorev, owner_user, other_user):
    baska = Mission.objects.create(name="Baska gorev", created_by=other_user)
    _bulgu(rollu_gorev, owner_user, 0, baslik="A")
    _bulgu(baska, other_user, 0, baslik="X")

    sonuc = gorevi_kumele(rollu_gorev, esik_metre=ESIK)
    assert sonuc["kumelenen_bulgu"] == 1
    assert Finding.objects.get(title="X").cluster_id is None


# --- Determinizm ve idempotanslik ----------------------------------------


def test_ikinci_kosu_ayni_sonucu_veriyor(rollu_gorev, owner_user):
    for sira, metre in enumerate([0, 10, 500]):
        _bulgu(rollu_gorev, owner_user, metre, baslik=chr(65 + sira))

    birinci = gorevi_kumele(rollu_gorev, esik_metre=ESIK)
    birinci_uyelik = _uyelikler(rollu_gorev)
    ikinci = gorevi_kumele(rollu_gorev, esik_metre=ESIK)

    assert birinci["kume_sayisi"] == ikinci["kume_sayisi"]
    assert birinci_uyelik == _uyelikler(rollu_gorev)


def test_girdi_sirasi_degisse_de_ayni_gruplama(rollu_gorev, owner_user, other_user):
    ileri = Mission.objects.create(name="Ileri", created_by=owner_user)
    geri = Mission.objects.create(name="Geri", created_by=owner_user)

    for metre in [0, 10, 500]:
        _bulgu(ileri, owner_user, metre)
    for metre in [500, 10, 0]:
        _bulgu(geri, owner_user, metre)

    gorevi_kumele(ileri, esik_metre=ESIK)
    gorevi_kumele(geri, esik_metre=ESIK)

    boyutlar_ileri = sorted(len(g["finding_ids"]) for g in kume_ozeti(ileri))
    boyutlar_geri = sorted(len(g["finding_ids"]) for g in kume_ozeti(geri))
    assert boyutlar_ileri == boyutlar_geri == [1, 2]


def test_gecersiz_esik_reddediliyor(rollu_gorev):
    with pytest.raises(ValueError):
        gorevi_kumele(rollu_gorev, esik_metre=0)


# --- Kume ozeti -----------------------------------------------------------


def test_kume_ozeti_merkez_ve_uye_sayisi_veriyor(rollu_gorev, owner_user):
    _bulgu(rollu_gorev, owner_user, 0, baslik="A")
    _bulgu(rollu_gorev, owner_user, 10, baslik="B")
    gorevi_kumele(rollu_gorev, esik_metre=ESIK)

    ozet = kume_ozeti(rollu_gorev)
    assert len(ozet) == 1
    assert ozet[0]["uye_sayisi"] == 2
    # GeoJSON sirasi: [boylam, enlem]
    assert ozet[0]["merkez"][0] == pytest.approx(TABAN_BOYLAM, abs=1e-3)
    assert ozet[0]["merkez"][1] == pytest.approx(TABAN_ENLEM, abs=1e-6)
    assert "olculmus konum degildir" in ozet[0]["merkez_notu"]


# --- API ------------------------------------------------------------------


def test_operator_kumeleme_calistirabiliyor(rollu_gorev, operator_user, owner_user, istemci_yap):
    _bulgu(rollu_gorev, owner_user, 0, baslik="A")
    _bulgu(rollu_gorev, owner_user, 10, baslik="B")

    yanit = istemci_yap(operator_user).post(
        reverse("mission-clusters", args=[rollu_gorev.id]),
        {"esik_metre": ESIK}, format="json",
    )

    assert yanit.status_code == 200
    assert yanit.data["kume_sayisi"] == 1
    assert yanit.data["clusters"][0]["uye_sayisi"] == 2


def test_viewer_kumeleme_calistiramiyor(rollu_gorev, viewer_user, istemci_yap):
    yanit = istemci_yap(viewer_user).post(
        reverse("mission-clusters", args=[rollu_gorev.id]), {}, format="json"
    )
    assert yanit.status_code == 403


def test_viewer_kume_ozetini_okuyabiliyor(rollu_gorev, viewer_user, istemci_yap):
    yanit = istemci_yap(viewer_user).get(reverse("mission-clusters", args=[rollu_gorev.id]))
    assert yanit.status_code == 200
    assert "esik_metre_varsayilan" in yanit.data


def test_uye_olmayan_kumeleme_calistiramiyor(rollu_gorev, yabanci_user, istemci_yap):
    yanit = istemci_yap(yabanci_user).post(
        reverse("mission-clusters", args=[rollu_gorev.id]), {}, format="json"
    )
    assert yanit.status_code == 404


def test_gecersiz_esik_api_400(rollu_gorev, operator_user, istemci_yap):
    for esik in (0, -5, "abc"):
        yanit = istemci_yap(operator_user).post(
            reverse("mission-clusters", args=[rollu_gorev.id]),
            {"esik_metre": esik}, format="json",
        )
        assert yanit.status_code == 400, esik
