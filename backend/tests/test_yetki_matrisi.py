"""Rol/islem matrisi ve /media/ bypass'inin kapali oldugu.

Buradaki testler yetki kurallarini TEK TEK degil TOPLU dogrular: her islem
dort kullanici sinifiyla (owner, operator, viewer, uye olmayan) denenir ve
donen kod beklenenle karsilastirilir. Matrisin kendisi
reports/hafta6_yetki_matrisi.csv dosyasina ayri bir script ile yazilir; bu
test o dosyanin dogrulugunun dayanagidir.
"""
import pytest
from django.urls import reverse

from core.models import Finding, MissionMember

pytestmark = pytest.mark.django_db


def _beklenen(owner, operator, viewer, yabanci):
    return {"owner": owner, "operator": operator, "viewer": viewer, "yabanci": yabanci}


@pytest.fixture
def roller(owner_user, operator_user, viewer_user, yabanci_user):
    return {
        "owner": owner_user,
        "operator": operator_user,
        "viewer": viewer_user,
        "yabanci": yabanci_user,
    }


def _kod(yanit):
    return yanit.status_code


# --- Okuma islemleri ------------------------------------------------------


def test_gorev_ayrintisi_matrisi(rollu_gorev, roller, istemci_yap):
    beklenen = _beklenen(200, 200, 200, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).get(reverse("mission-detail", args=[rollu_gorev.id]))
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_kare_listesi_matrisi(rollu_gorev, roller, istemci_yap):
    beklenen = _beklenen(200, 200, 200, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).get(reverse("mission-frames", args=[rollu_gorev.id]))
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_kosu_listesi_matrisi(rollu_gorev, roller, istemci_yap):
    beklenen = _beklenen(200, 200, 200, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).get(reverse("mission-runs", args=[rollu_gorev.id]))
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_uye_listesi_matrisi(rollu_gorev, roller, istemci_yap):
    beklenen = _beklenen(200, 200, 200, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).get(reverse("mission-members", args=[rollu_gorev.id]))
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_denetim_listesi_matrisi(rollu_gorev, roller, istemci_yap):
    beklenen = _beklenen(200, 200, 200, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).get(reverse("mission-audit", args=[rollu_gorev.id]))
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_bulgu_listesi_matrisi(rollu_gorev, roller, istemci_yap):
    beklenen = _beklenen(200, 200, 200, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).get(reverse("mission-findings", args=[rollu_gorev.id]))
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_tespit_listesi_matrisi(tespitli_kosu, roller, istemci_yap):
    run, _ = tespitli_kosu
    beklenen = _beklenen(200, 200, 200, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).get(reverse("run-detections", args=[run.id]))
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


# --- Yazma islemleri ------------------------------------------------------


def test_kare_ekleme_matrisi(rollu_gorev, roller, istemci_yap, make_image):
    beklenen = _beklenen(201, 201, 403, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).post(
            reverse("mission-frames", args=[rollu_gorev.id]),
            {"images": make_image(name=f"{rol}.jpg", color=(len(rol) * 7, 30, 60))},
        )
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_tarama_baslatma_matrisi(rollu_gorev, roller, istemci_yap, model_version,
                                 celery_eager, django_capture_on_commit_callbacks):
    beklenen = _beklenen(202, 202, 403, 404)
    for rol, kullanici in roller.items():
        with django_capture_on_commit_callbacks(execute=True):
            yanit = istemci_yap(kullanici).post(
                reverse("mission-runs", args=[rollu_gorev.id]),
                {"model_version_id": model_version.id}, format="json",
            )
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_inceleme_yazma_matrisi(tespitli_kosu, roller, istemci_yap):
    _, detection = tespitli_kosu
    # owner ve operator ilk kez yazdiginda 201, viewer 403, yabanci 404
    beklenen = _beklenen(201, 201, 403, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).put(
            reverse("detection-reviews", args=[detection.id]),
            {"decision": "accepted"}, format="json",
        )
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_bulgu_olusturma_matrisi(rollu_gorev, roller, istemci_yap):
    beklenen = _beklenen(201, 201, 403, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).post(
            reverse("mission-findings", args=[rollu_gorev.id]),
            {"location_source": "none", "title": rol}, format="json",
        )
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_kumeleme_calistirma_matrisi(rollu_gorev, roller, istemci_yap):
    beklenen = _beklenen(200, 200, 403, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).post(
            reverse("mission-clusters", args=[rollu_gorev.id]), {}, format="json"
        )
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_uye_ekleme_matrisi(rollu_gorev, roller, istemci_yap, django_user_model):
    # Her rol icin ayri bir aday kullanici: basarili ekleme digerini etkilemesin.
    beklenen = _beklenen(201, 403, 403, 404)
    for rol, kullanici in roller.items():
        aday = django_user_model.objects.create_user(
            username=f"aday_{rol}", password="gizli-parola-aday"
        )
        yanit = istemci_yap(kullanici).post(
            reverse("mission-members", args=[rollu_gorev.id]),
            {"username": aday.username, "role": "viewer"}, format="json",
        )
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_rol_degistirme_matrisi(rollu_gorev, roller, istemci_yap, viewer_user):
    uyelik = MissionMember.objects.get(mission=rollu_gorev, user=viewer_user)
    beklenen = _beklenen(200, 403, 403, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).patch(
            reverse("mission-member-detail", args=[rollu_gorev.id, uyelik.id]),
            {"role": "viewer"}, format="json",
        )
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_bulgu_silme_matrisi(rollu_gorev, roller, istemci_yap, owner_user):
    beklenen = _beklenen(204, 204, 403, 404)
    for rol, kullanici in roller.items():
        bulgu = Finding.objects.create(
            mission=rollu_gorev, location_source="none", created_by=owner_user
        )
        yanit = istemci_yap(kullanici).delete(
            reverse("finding-detail", args=[bulgu.id])
        )
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


# --- Denetim kaydi yazma ucu YOK -----------------------------------------


def test_denetim_yazma_hicbir_rolde_mumkun_degil(rollu_gorev, roller, istemci_yap):
    """AuditLog'a API uzerinden yazma ucu yoktur; owner bile yazamaz."""
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).post(
            reverse("mission-audit", args=[rollu_gorev.id]),
            {"action": "member_added"}, format="json",
        )
        # Uye olmayan zaten 404 alir; uyeler icin yontem desteklenmiyor.
        assert _kod(yanit) in (404, 405), f"{rol}: {_kod(yanit)}"


# --- Goruntu erisimi ve /media/ bypass -----------------------------------


def test_kare_goruntusu_matrisi(rollu_gorev, roller, istemci_yap):
    from core.models import Frame

    kare = Frame.objects.filter(mission=rollu_gorev).first()
    beklenen = _beklenen(200, 200, 200, 404)
    for rol, kullanici in roller.items():
        yanit = istemci_yap(kullanici).get(reverse("frame-image", args=[kare.id]))
        assert _kod(yanit) == beklenen[rol], f"{rol}: {_kod(yanit)}"


def test_media_yolu_artik_servis_edilmiyor(rollu_gorev, api_client, settings):
    """MissionMember denetimini dolasan /media/ yolu kapatilmis olmali.

    DEBUG acikken bile Django artik media dosyasi sunmuyor; goruntuye tek
    erisim kimlik dogrulamali uctan.
    """
    from core.models import Frame

    settings.DEBUG = True
    kare = Frame.objects.filter(mission=rollu_gorev).first()

    yanit = api_client.get(f"/media/{kare.image.name}")
    assert yanit.status_code == 404


def test_media_yolu_uye_icin_de_servis_edilmiyor(rollu_gorev, owner_user, istemci_yap):
    """Uye olmak bile /media/ yolunu acmiyor: o yol tamamen kapali."""
    from core.models import Frame

    kare = Frame.objects.filter(mission=rollu_gorev).first()
    yanit = istemci_yap(owner_user).get(f"/media/{kare.image.name}")
    assert yanit.status_code == 404


def test_goruntu_ucu_yol_gecisine_kapali(rollu_gorev, owner_user, istemci_yap):
    """Uc yalnizca birincil anahtar aliyor; yol parcasi kabul etmiyor."""
    istemci = istemci_yap(owner_user)
    for deneme in ("../../etc/passwd", "1/../../2", "%2e%2e%2fetc%2fpasswd"):
        yanit = istemci.get(f"/api/frames/{deneme}/image/")
        assert yanit.status_code == 404, deneme


def test_kimliksiz_kullanici_goruntuye_erisemiyor(rollu_gorev, api_client):
    from core.models import Frame

    kare = Frame.objects.filter(mission=rollu_gorev).first()
    yanit = api_client.get(reverse("frame-image", args=[kare.id]))
    assert yanit.status_code in (401, 403)
