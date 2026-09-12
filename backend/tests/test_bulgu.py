"""Cografi bulgu: PointField, SRID, provenance ve koordinat dogrulugu."""
import pytest
from django.contrib.gis.geos import Point
from django.db import IntegrityError, transaction
from django.urls import reverse

from core.models import Finding

pytestmark = pytest.mark.django_db


def _bulgu_yolu(mission):
    return reverse("mission-findings", args=[mission.id])


# --- Model seviyesi -------------------------------------------------------


def test_konum_srid_4326_olarak_saklaniyor(rollu_gorev, owner_user):
    bulgu = Finding.objects.create(
        mission=rollu_gorev,
        location=Point(16.44, 43.51, srid=4326),
        location_source=Finding.LocationSource.MANUAL,
        created_by=owner_user,
    )
    bulgu.refresh_from_db()

    assert bulgu.location.srid == 4326
    # Point(x, y) = Point(boylam, enlem)
    assert bulgu.location.x == pytest.approx(16.44)
    assert bulgu.location.y == pytest.approx(43.51)


def test_konumsuz_bulgu_kaydedilebiliyor(rollu_gorev, owner_user):
    bulgu = Finding.objects.create(
        mission=rollu_gorev, location=None,
        location_source=Finding.LocationSource.NONE, created_by=owner_user,
    )
    bulgu.refresh_from_db()

    assert bulgu.location is None
    assert not bulgu.has_measured_location


def test_konumsuz_kayit_sifir_sifir_degildir(rollu_gorev, owner_user):
    """Null konum ile 0,0 AYNI SEY DEGIL; 0,0 Gine Korfezi'nde gercek bir nokta."""
    konumsuz = Finding.objects.create(
        mission=rollu_gorev, location=None,
        location_source=Finding.LocationSource.NONE, created_by=owner_user,
    )
    sifir_noktasi = Finding.objects.create(
        mission=rollu_gorev, location=Point(0.0, 0.0, srid=4326),
        location_source=Finding.LocationSource.MANUAL, created_by=owner_user,
    )

    assert konumsuz.location is None
    assert sifir_noktasi.location is not None
    assert (sifir_noktasi.location.x, sifir_noktasi.location.y) == (0.0, 0.0)
    assert Finding.objects.filter(location__isnull=True).count() == 1


def test_kisit_konumsuz_kayda_kaynak_iddiasi_engelliyor(rollu_gorev, owner_user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Finding.objects.create(
                mission=rollu_gorev, location=None,
                location_source=Finding.LocationSource.EXIF, created_by=owner_user,
            )


def test_kisit_kaynaksiz_koordinati_engelliyor(rollu_gorev, owner_user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Finding.objects.create(
                mission=rollu_gorev, location=Point(10.0, 20.0, srid=4326),
                location_source=Finding.LocationSource.NONE, created_by=owner_user,
            )


def test_demo_ve_olculmus_kaynak_ayirt_edilebiliyor(rollu_gorev, owner_user):
    demo = Finding.objects.create(
        mission=rollu_gorev, location=Point(16.0, 43.0, srid=4326),
        location_source=Finding.LocationSource.DEMO, created_by=owner_user,
    )
    elle = Finding.objects.create(
        mission=rollu_gorev, location=Point(16.1, 43.1, srid=4326),
        location_source=Finding.LocationSource.MANUAL, created_by=owner_user,
    )

    assert demo.is_demo and not elle.is_demo
    # Elle girilen konum da OLCULMUS sayilmaz: beyandir.
    assert not demo.has_measured_location
    assert not elle.has_measured_location
    assert Finding.objects.filter(location_source="demo").count() == 1


# --- API ------------------------------------------------------------------


def test_operator_konumsuz_bulgu_olusturabiliyor(rollu_gorev, operator_user, istemci_yap):
    yanit = istemci_yap(operator_user).post(
        _bulgu_yolu(rollu_gorev),
        {"title": "Konumsuz aday", "location_source": "none"},
        format="json",
    )

    assert yanit.status_code == 201
    assert yanit.data["location"] is None
    assert yanit.data["latitude"] is None and yanit.data["longitude"] is None


def test_geojson_koordinat_sirasi_boylam_once(rollu_gorev, operator_user, istemci_yap):
    """RFC 7946: GeoJSON coordinates = [longitude, latitude]."""
    yanit = istemci_yap(operator_user).post(
        _bulgu_yolu(rollu_gorev),
        {"latitude": 43.51, "longitude": 16.44, "location_source": "manual"},
        format="json",
    )

    assert yanit.status_code == 201
    assert yanit.data["location"]["type"] == "Point"
    assert yanit.data["location"]["coordinates"] == [
        pytest.approx(16.44), pytest.approx(43.51)
    ]
    # Ayri alanlar sirayi belirsiz birakmiyor.
    assert yanit.data["latitude"] == pytest.approx(43.51)
    assert yanit.data["longitude"] == pytest.approx(16.44)


def test_enlem_araligi_dogrulaniyor(rollu_gorev, operator_user, istemci_yap):
    yanit = istemci_yap(operator_user).post(
        _bulgu_yolu(rollu_gorev),
        {"latitude": 91.0, "longitude": 16.0, "location_source": "manual"},
        format="json",
    )
    assert yanit.status_code == 400


def test_boylam_araligi_dogrulaniyor(rollu_gorev, operator_user, istemci_yap):
    yanit = istemci_yap(operator_user).post(
        _bulgu_yolu(rollu_gorev),
        {"latitude": 43.0, "longitude": 181.0, "location_source": "manual"},
        format="json",
    )
    assert yanit.status_code == 400


def test_tek_basina_enlem_reddediliyor(rollu_gorev, operator_user, istemci_yap):
    yanit = istemci_yap(operator_user).post(
        _bulgu_yolu(rollu_gorev),
        {"latitude": 43.0, "location_source": "manual"},
        format="json",
    )
    assert yanit.status_code == 400


def test_koordinatla_none_kaynagi_celisiyor(rollu_gorev, operator_user, istemci_yap):
    yanit = istemci_yap(operator_user).post(
        _bulgu_yolu(rollu_gorev),
        {"latitude": 43.0, "longitude": 16.0, "location_source": "none"},
        format="json",
    )
    assert yanit.status_code == 400


def test_olculmus_kaynak_elle_secilemiyor(rollu_gorev, operator_user, istemci_yap):
    """Operator uydurma bir koordinati 'EXIF' diye kaydedememeli."""
    for kaynak in ("exif", "flight_log"):
        yanit = istemci_yap(operator_user).post(
            _bulgu_yolu(rollu_gorev),
            {"latitude": 43.0, "longitude": 16.0, "location_source": kaynak},
            format="json",
        )
        assert yanit.status_code == 400, kaynak


def test_demo_bulgu_api_yanitinda_etiketli(rollu_gorev, operator_user, istemci_yap):
    yanit = istemci_yap(operator_user).post(
        _bulgu_yolu(rollu_gorev),
        {"latitude": 43.0, "longitude": 16.0, "location_source": "demo"},
        format="json",
    )

    assert yanit.status_code == 201
    assert yanit.data["is_demo"] is True
    assert yanit.data["location_source"] == "demo"
    assert yanit.data["has_measured_location"] is False


def test_demo_suzgeci_calisiyor(rollu_gorev, operator_user, istemci_yap):
    istemci = istemci_yap(operator_user)
    istemci.post(_bulgu_yolu(rollu_gorev),
                 {"latitude": 43.0, "longitude": 16.0, "location_source": "demo"},
                 format="json")
    istemci.post(_bulgu_yolu(rollu_gorev),
                 {"latitude": 43.1, "longitude": 16.1, "location_source": "manual"},
                 format="json")

    demo = istemci.get(_bulgu_yolu(rollu_gorev) + "?demo=true")
    gercek = istemci.get(_bulgu_yolu(rollu_gorev) + "?demo=false")

    assert demo.data["count"] == 1 and demo.data["results"][0]["is_demo"] is True
    assert gercek.data["count"] == 1 and gercek.data["results"][0]["is_demo"] is False


# --- Yetki ----------------------------------------------------------------


def test_viewer_bulgu_olusturamaz(rollu_gorev, viewer_user, istemci_yap):
    yanit = istemci_yap(viewer_user).post(
        _bulgu_yolu(rollu_gorev), {"location_source": "none"}, format="json"
    )
    assert yanit.status_code == 403
    assert not Finding.objects.filter(mission=rollu_gorev).exists()


def test_viewer_bulgulari_okuyabilir(rollu_gorev, owner_user, viewer_user, istemci_yap):
    istemci_yap(owner_user).post(
        _bulgu_yolu(rollu_gorev), {"location_source": "none"}, format="json"
    )
    yanit = istemci_yap(viewer_user).get(_bulgu_yolu(rollu_gorev))
    assert yanit.status_code == 200 and yanit.data["count"] == 1


def test_uye_olmayan_bulgulari_goremez(rollu_gorev, owner_user, yabanci_user, istemci_yap):
    istemci_yap(owner_user).post(
        _bulgu_yolu(rollu_gorev), {"location_source": "none"}, format="json"
    )
    yanit = istemci_yap(yabanci_user).get(_bulgu_yolu(rollu_gorev))
    assert yanit.status_code == 404


def test_baska_gorevin_bulgusu_kimlik_tahminiyle_degistirilemez(
    rollu_gorev, owner_user, other_user, istemci_yap
):
    from core.models import Mission

    baska = Mission.objects.create(name="Baska", created_by=other_user)
    bulgu = Finding.objects.create(
        mission=baska, location_source=Finding.LocationSource.NONE, created_by=other_user
    )

    yanit = istemci_yap(owner_user).patch(
        reverse("finding-detail", args=[bulgu.id]),
        {"location_source": "none", "title": "ele gecirildi"},
        format="json",
    )

    assert yanit.status_code == 404
    bulgu.refresh_from_db()
    assert bulgu.title == ""


def test_bulgu_guncellenince_kume_sonucu_gecersizlesiyor(
    rollu_gorev, operator_user, istemci_yap
):
    bulgu = Finding.objects.create(
        mission=rollu_gorev, location=Point(16.0, 43.0, srid=4326),
        location_source=Finding.LocationSource.MANUAL, created_by=operator_user,
        cluster_id=3, cluster_key="gercek",
    )

    yanit = istemci_yap(operator_user).patch(
        reverse("finding-detail", args=[bulgu.id]),
        {"latitude": 44.0, "longitude": 17.0, "location_source": "manual"},
        format="json",
    )

    assert yanit.status_code == 200
    bulgu.refresh_from_db()
    assert bulgu.cluster_id is None and bulgu.cluster_key == ""
