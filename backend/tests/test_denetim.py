"""Denetim kaydi: degistirilemezlik, kapsam ve hassas veri sizmamasi."""
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from core.denetim import degisiklik_ozeti, denetim_yaz
from core.models import AuditLog, Finding, MissionMember, Review

pytestmark = pytest.mark.django_db


# --- Degistirilemezlik ----------------------------------------------------


def test_denetim_kaydi_guncellenemiyor(rollu_gorev, owner_user):
    kayit = denetim_yaz(
        actor=owner_user, mission=rollu_gorev,
        action=AuditLog.Action.REVIEW_CREATED, object_type="Review", object_id="1",
    )
    kayit.action = AuditLog.Action.FINDING_DELETED

    with pytest.raises(ValidationError):
        kayit.save()


def test_denetim_kaydi_silinemiyor(rollu_gorev, owner_user):
    kayit = denetim_yaz(
        actor=owner_user, mission=rollu_gorev,
        action=AuditLog.Action.REVIEW_CREATED, object_type="Review", object_id="1",
    )
    with pytest.raises(ValidationError):
        kayit.delete()

    assert AuditLog.objects.filter(pk=kayit.pk).exists()


def test_denetim_ucunda_yazma_yontemi_yok(rollu_gorev, owner_user, istemci_yap):
    istemci = istemci_yap(owner_user)
    yol = reverse("mission-audit", args=[rollu_gorev.id])

    assert istemci.post(yol, {}, format="json").status_code == 405
    assert istemci.put(yol, {}, format="json").status_code == 405
    assert istemci.delete(yol).status_code == 405


# --- Kapsam ---------------------------------------------------------------


def test_uye_ekleme_denetime_yaziliyor(rollu_gorev, owner_user, yabanci_user, istemci_yap):
    istemci_yap(owner_user).post(
        reverse("mission-members", args=[rollu_gorev.id]),
        {"username": yabanci_user.username, "role": "operator"},
        format="json",
    )

    kayit = AuditLog.objects.filter(action=AuditLog.Action.MEMBER_ADDED).first()
    assert kayit is not None
    assert kayit.actor == owner_user
    assert kayit.mission == rollu_gorev


def test_rol_degisikligi_onceki_ve_sonraki_ile_yaziliyor(
    rollu_gorev, owner_user, viewer_user, istemci_yap
):
    uyelik = MissionMember.objects.get(mission=rollu_gorev, user=viewer_user)
    istemci_yap(owner_user).patch(
        reverse("mission-member-detail", args=[rollu_gorev.id, uyelik.id]),
        {"role": "operator"}, format="json",
    )

    kayit = AuditLog.objects.get(action=AuditLog.Action.MEMBER_ROLE_CHANGED)
    assert kayit.changes["role"] == {"onceki": "viewer", "sonraki": "operator"}


def test_uye_cikarma_denetime_yaziliyor(rollu_gorev, owner_user, viewer_user, istemci_yap):
    uyelik = MissionMember.objects.get(mission=rollu_gorev, user=viewer_user)
    istemci_yap(owner_user).delete(
        reverse("mission-member-detail", args=[rollu_gorev.id, uyelik.id])
    )
    assert AuditLog.objects.filter(action=AuditLog.Action.MEMBER_REMOVED).exists()


def test_inceleme_olusturma_ve_guncelleme_ayri_kaydediliyor(
    tespitli_kosu, operator_user, istemci_yap
):
    _, detection = tespitli_kosu
    istemci = istemci_yap(operator_user)
    yol = reverse("detection-reviews", args=[detection.id])

    istemci.put(yol, {"decision": "accepted"}, format="json")
    istemci.put(yol, {"decision": "rejected"}, format="json")

    assert AuditLog.objects.filter(action=AuditLog.Action.REVIEW_CREATED).count() == 1
    guncelleme = AuditLog.objects.get(action=AuditLog.Action.REVIEW_UPDATED)
    assert guncelleme.changes["decision"] == {"onceki": "accepted", "sonraki": "rejected"}


def test_bulgu_islemleri_denetime_yaziliyor(rollu_gorev, operator_user, istemci_yap):
    istemci = istemci_yap(operator_user)
    olustur = istemci.post(
        reverse("mission-findings", args=[rollu_gorev.id]),
        {"location_source": "none", "title": "ilk"}, format="json",
    )
    bulgu_id = olustur.data["id"]
    istemci.patch(
        reverse("finding-detail", args=[bulgu_id]),
        {"location_source": "none", "title": "ikinci"}, format="json",
    )
    istemci.delete(reverse("finding-detail", args=[bulgu_id]))

    eylemler = set(AuditLog.objects.values_list("action", flat=True))
    assert {"finding_created", "finding_updated", "finding_deleted"} <= eylemler


def test_kumeleme_denetime_yaziliyor(rollu_gorev, operator_user, istemci_yap):
    istemci_yap(operator_user).post(
        reverse("mission-clusters", args=[rollu_gorev.id]),
        {"esik_metre": 50}, format="json",
    )
    kayit = AuditLog.objects.get(action=AuditLog.Action.CLUSTER_RUN)
    assert kayit.changes["esik_metre"] == 50.0


# --- Basarisiz islem denetim uretmez ------------------------------------


def test_basarisiz_rol_degisikligi_denetim_kaydi_uretmiyor(
    rollu_gorev, owner_user, istemci_yap
):
    """Son owner dusurulemez; islem reddedilince gecmis de yazilmamali."""
    uyelik = MissionMember.objects.get(mission=rollu_gorev, user=owner_user)
    onceki_sayi = AuditLog.objects.count()

    yanit = istemci_yap(owner_user).patch(
        reverse("mission-member-detail", args=[rollu_gorev.id, uyelik.id]),
        {"role": "viewer"}, format="json",
    )

    assert yanit.status_code == 400
    assert AuditLog.objects.count() == onceki_sayi


def test_yetkisiz_inceleme_denemesi_denetim_uretmiyor(
    tespitli_kosu, viewer_user, istemci_yap
):
    _, detection = tespitli_kosu
    onceki_sayi = AuditLog.objects.count()

    yanit = istemci_yap(viewer_user).put(
        reverse("detection-reviews", args=[detection.id]),
        {"decision": "accepted"}, format="json",
    )

    assert yanit.status_code == 403
    assert AuditLog.objects.count() == onceki_sayi


def test_islem_geri_alinirsa_denetim_de_geri_aliniyor(rollu_gorev, owner_user):
    """Denetim kaydi islemle AYNI transaction icinde yazilmali."""
    from django.db import transaction

    onceki_sayi = AuditLog.objects.count()

    class Bilerek(Exception):
        pass

    with pytest.raises(Bilerek):
        with transaction.atomic():
            Review.objects.none()  # islem yerine gecen bir yer tutucu
            denetim_yaz(
                actor=owner_user, mission=rollu_gorev,
                action=AuditLog.Action.FINDING_CREATED,
                object_type="Finding", object_id="99",
            )
            raise Bilerek()

    assert AuditLog.objects.count() == onceki_sayi


# --- Hassas veri ----------------------------------------------------------


def test_hassas_anahtarlar_denetime_yazilmiyor():
    ozet = degisiklik_ozeti(
        onceki={"password": "eski-parola", "role": "viewer"},
        sonraki={
            "password": "yeni-parola", "token": "eyJhbGciOi", "role": "owner",
            "email": "kisi@ornek.test", "access": "gizli",
        },
    )

    assert set(ozet) == {"role"}
    metin = str(ozet)
    assert "parola" not in metin and "eyJhbGciOi" not in metin
    assert "kisi@ornek.test" not in metin


def test_uzun_degerler_kirpiliyor():
    ozet = degisiklik_ozeti(onceki={"note": ""}, sonraki={"note": "x" * 5000})
    assert len(ozet["note"]["sonraki"]) < 300


def test_degismeyen_alan_yazilmiyor():
    ozet = degisiklik_ozeti(
        onceki={"a": 1, "b": 2}, sonraki={"a": 1, "b": 3}
    )
    assert set(ozet) == {"b"}


def test_denetim_yanitinda_parola_veya_token_yok(
    rollu_gorev, owner_user, yabanci_user, istemci_yap
):
    istemci = istemci_yap(owner_user)
    istemci.post(
        reverse("mission-members", args=[rollu_gorev.id]),
        {"username": yabanci_user.username, "role": "operator"}, format="json",
    )

    yanit = istemci.get(reverse("mission-audit", args=[rollu_gorev.id]))
    govde = str(yanit.data).lower()

    assert yanit.status_code == 200
    for yasak in ("password", "parola", "token", "pbkdf2", "bearer"):
        assert yasak not in govde, yasak


# --- Yetki ----------------------------------------------------------------


def test_viewer_denetimi_okuyabilir(rollu_gorev, viewer_user, istemci_yap):
    yanit = istemci_yap(viewer_user).get(reverse("mission-audit", args=[rollu_gorev.id]))
    assert yanit.status_code == 200


def test_uye_olmayan_denetimi_okuyamaz(rollu_gorev, yabanci_user, istemci_yap):
    yanit = istemci_yap(yabanci_user).get(reverse("mission-audit", args=[rollu_gorev.id]))
    assert yanit.status_code == 404


def test_denetim_baska_gorevin_kaydini_gostermiyor(
    rollu_gorev, owner_user, other_user, istemci_yap
):
    from core.models import Mission

    baska = Mission.objects.create(name="Baska", created_by=other_user)
    denetim_yaz(
        actor=other_user, mission=baska,
        action=AuditLog.Action.FINDING_CREATED, object_type="Finding", object_id="1",
    )

    yanit = istemci_yap(owner_user).get(reverse("mission-audit", args=[rollu_gorev.id]))
    assert yanit.data["count"] == 0
