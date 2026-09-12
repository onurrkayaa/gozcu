"""Operator incelemesi: kisit, yetki ve Detection'dan ayriligi."""
import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from core.models import Detection, Review

pytestmark = pytest.mark.django_db


def _inceleme_yolu(detection):
    return reverse("detection-reviews", args=[detection.id])


# --- Temel davranis -------------------------------------------------------


def test_operator_inceleme_yazabilir(tespitli_kosu, operator_user, istemci_yap):
    _, detection = tespitli_kosu
    yanit = istemci_yap(operator_user).put(
        _inceleme_yolu(detection), {"decision": "accepted", "note": "Kisi gorunuyor"},
        format="json",
    )

    assert yanit.status_code == 201
    inceleme = Review.objects.get(detection=detection, reviewer=operator_user)
    assert inceleme.decision == Review.Decision.ACCEPTED
    assert inceleme.note == "Kisi gorunuyor"


def test_inceleme_detection_kaydini_degistirmiyor(tespitli_kosu, operator_user, istemci_yap):
    """Model ciktisi ile insan yargisi ayri kalmali."""
    _, detection = tespitli_kosu
    onceki = Detection.objects.filter(pk=detection.pk).values().first()

    istemci_yap(operator_user).put(
        _inceleme_yolu(detection), {"decision": "rejected"}, format="json"
    )

    sonraki = Detection.objects.filter(pk=detection.pk).values().first()
    assert onceki == sonraki


def test_ayni_kullanici_kararini_gunceller_yeni_kayit_acmaz(
    tespitli_kosu, operator_user, istemci_yap
):
    _, detection = tespitli_kosu
    istemci = istemci_yap(operator_user)

    ilk = istemci.put(_inceleme_yolu(detection), {"decision": "uncertain"}, format="json")
    ikinci = istemci.put(_inceleme_yolu(detection), {"decision": "accepted"}, format="json")

    assert ilk.status_code == 201
    assert ikinci.status_code == 200
    assert Review.objects.filter(detection=detection, reviewer=operator_user).count() == 1
    assert Review.objects.get(detection=detection, reviewer=operator_user).decision == "accepted"


def test_iki_operator_ayni_tespitte_farkli_karar_verebilir(
    tespitli_kosu, owner_user, operator_user, istemci_yap
):
    """Anlasmazlik bilgisi korunmali: biri digerinin kararini ezmez."""
    _, detection = tespitli_kosu

    istemci_yap(owner_user).put(
        _inceleme_yolu(detection), {"decision": "accepted"}, format="json"
    )
    istemci_yap(operator_user).put(
        _inceleme_yolu(detection), {"decision": "rejected"}, format="json"
    )

    kararlar = dict(
        Review.objects.filter(detection=detection).values_list("reviewer__username", "decision")
    )
    assert kararlar == {"sahip": "accepted", "operator": "rejected"}


def test_veritabani_ayni_inceleyenden_iki_kayit_kabul_etmiyor(
    tespitli_kosu, operator_user
):
    _, detection = tespitli_kosu
    Review.objects.create(detection=detection, reviewer=operator_user, decision="accepted")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Review.objects.create(
                detection=detection, reviewer=operator_user, decision="rejected"
            )


def test_gecersiz_karar_reddediliyor(tespitli_kosu, operator_user, istemci_yap):
    _, detection = tespitli_kosu
    yanit = istemci_yap(operator_user).put(
        _inceleme_yolu(detection), {"decision": "belki"}, format="json"
    )
    assert yanit.status_code == 400


# --- Yetki ----------------------------------------------------------------


def test_viewer_inceleme_yazamaz(tespitli_kosu, viewer_user, istemci_yap):
    _, detection = tespitli_kosu
    yanit = istemci_yap(viewer_user).put(
        _inceleme_yolu(detection), {"decision": "accepted"}, format="json"
    )

    assert yanit.status_code == 403
    assert not Review.objects.filter(detection=detection).exists()


def test_viewer_incelemeleri_okuyabilir(tespitli_kosu, owner_user, viewer_user, istemci_yap):
    _, detection = tespitli_kosu
    istemci_yap(owner_user).put(
        _inceleme_yolu(detection), {"decision": "accepted"}, format="json"
    )

    yanit = istemci_yap(viewer_user).get(_inceleme_yolu(detection))
    assert yanit.status_code == 200
    assert len(yanit.data) == 1


def test_uye_olmayan_inceleme_okuyamaz(tespitli_kosu, yabanci_user, istemci_yap):
    _, detection = tespitli_kosu
    yanit = istemci_yap(yabanci_user).get(_inceleme_yolu(detection))
    assert yanit.status_code == 404


def test_uye_olmayan_inceleme_yazamaz(tespitli_kosu, yabanci_user, istemci_yap):
    _, detection = tespitli_kosu
    yanit = istemci_yap(yabanci_user).put(
        _inceleme_yolu(detection), {"decision": "accepted"}, format="json"
    )

    assert yanit.status_code == 404
    assert not Review.objects.filter(detection=detection).exists()


def test_kimliksiz_erisim_reddediliyor(tespitli_kosu, api_client):
    _, detection = tespitli_kosu
    assert api_client.get(_inceleme_yolu(detection)).status_code in (401, 403)


def test_kosu_incelemeleri_toplu_listeleniyor(
    tespitli_kosu, owner_user, operator_user, istemci_yap
):
    run, detection = tespitli_kosu
    istemci_yap(owner_user).put(
        _inceleme_yolu(detection), {"decision": "accepted"}, format="json"
    )
    istemci_yap(operator_user).put(
        _inceleme_yolu(detection), {"decision": "uncertain"}, format="json"
    )

    yanit = istemci_yap(operator_user).get(reverse("run-reviews", args=[run.id]))
    assert yanit.status_code == 200
    assert yanit.data["count"] == 2


def test_baska_gorevin_kosu_incelemeleri_gorulemez(
    tespitli_kosu, yabanci_user, istemci_yap
):
    run, _ = tespitli_kosu
    yanit = istemci_yap(yabanci_user).get(reverse("run-reviews", args=[run.id]))
    assert yanit.status_code == 404
