"""Gorev uyeligi: backfill, tekillik, son sahip korumasi ve rol yonetimi."""
import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.urls import reverse

from core.models import Mission, MissionMember

pytestmark = pytest.mark.django_db


# --- Degismez: olusturanin uyeligi ---------------------------------------


def test_gorev_olusturulunca_sahibi_owner_uyesi_olur(user):
    """Sinyal her kod yolunda calismali: burada ORM uzerinden aciliyor."""
    mission = Mission.objects.create(name="ORM gorevi", created_by=user)

    uyelik = MissionMember.objects.get(mission=mission, user=user)
    assert uyelik.role == MissionMember.Role.OWNER


def test_api_uzerinden_olusturulan_gorevde_de_owner_uyeligi_var(auth_client, user):
    yanit = auth_client.post(reverse("mission-list"), {"name": "API gorevi"})

    assert yanit.status_code == 201
    uyelik = MissionMember.objects.get(mission_id=yanit.data["id"], user=user)
    assert uyelik.role == MissionMember.Role.OWNER


def test_olusturan_kendi_gorevini_listede_gorur(auth_client, user):
    Mission.objects.create(name="Gorunur", created_by=user)
    yanit = auth_client.get(reverse("mission-list"))
    assert yanit.data["count"] == 1


def test_ayni_kullanici_ayni_gorevde_iki_kez_uye_olamaz(user, other_user):
    mission = Mission.objects.create(name="Tekillik", created_by=user)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MissionMember.objects.create(
                mission=mission, user=user, role=MissionMember.Role.VIEWER
            )


# --- Erisim uyelige bagli ------------------------------------------------


def test_uye_olmayan_gorevi_listede_gormez(rollu_gorev, yabanci_user, istemci_yap):
    yanit = istemci_yap(yabanci_user).get(reverse("mission-list"))
    assert yanit.data["count"] == 0


def test_uye_olmayan_gorev_ayrintisinda_404_alir(rollu_gorev, yabanci_user, istemci_yap):
    yanit = istemci_yap(yabanci_user).get(reverse("mission-detail", args=[rollu_gorev.id]))
    assert yanit.status_code == 404


def test_viewer_gorevi_gorebilir(rollu_gorev, viewer_user, istemci_yap):
    yanit = istemci_yap(viewer_user).get(reverse("mission-detail", args=[rollu_gorev.id]))
    assert yanit.status_code == 200


def test_uyelikten_cikarilan_kullanici_erisimini_kaybeder(
    rollu_gorev, viewer_user, istemci_yap
):
    """created_by ile uyelik iki ayri yetki kaynagi olsaydi bu test gecmezdi."""
    istemci = istemci_yap(viewer_user)
    assert istemci.get(reverse("mission-detail", args=[rollu_gorev.id])).status_code == 200

    MissionMember.objects.filter(mission=rollu_gorev, user=viewer_user).delete()

    assert istemci.get(reverse("mission-detail", args=[rollu_gorev.id])).status_code == 404


def test_olusturan_uyelikten_cikarilirsa_erisemez(rollu_gorev, owner_user, istemci_yap):
    """Mission.created_by hala owner_user'i gosteriyor ama yetki uyelikte."""
    MissionMember.objects.filter(mission=rollu_gorev, user=owner_user).delete()

    yanit = istemci_yap(owner_user).get(reverse("mission-detail", args=[rollu_gorev.id]))
    assert yanit.status_code == 404
    assert rollu_gorev.created_by_id == owner_user.id


# --- Uye listeleme ve ekleme ---------------------------------------------


def test_uyeler_listeleniyor(rollu_gorev, viewer_user, istemci_yap):
    yanit = istemci_yap(viewer_user).get(reverse("mission-members", args=[rollu_gorev.id]))

    assert yanit.status_code == 200
    roller = {u["user"]["username"]: u["role"] for u in yanit.data["results"]}
    assert roller == {"sahip": "owner", "operator": "operator", "izleyici": "viewer"}


def test_uye_listesi_e_posta_sizdirmiyor(rollu_gorev, owner_user, istemci_yap):
    owner_user.email = "gizli@ornek.test"
    owner_user.save(update_fields=["email"])

    yanit = istemci_yap(owner_user).get(reverse("mission-members", args=[rollu_gorev.id]))

    assert "gizli@ornek.test" not in str(yanit.data)
    assert set(yanit.data["results"][0]["user"]) == {"id", "username"}


def test_owner_uye_ekleyebilir(rollu_gorev, owner_user, yabanci_user, istemci_yap):
    yanit = istemci_yap(owner_user).post(
        reverse("mission-members", args=[rollu_gorev.id]),
        {"username": yabanci_user.username, "role": "operator"},
        format="json",
    )

    assert yanit.status_code == 201
    assert MissionMember.objects.filter(
        mission=rollu_gorev, user=yabanci_user, role="operator"
    ).exists()


def test_operator_uye_ekleyemez(rollu_gorev, operator_user, yabanci_user, istemci_yap):
    yanit = istemci_yap(operator_user).post(
        reverse("mission-members", args=[rollu_gorev.id]),
        {"username": yabanci_user.username, "role": "viewer"},
        format="json",
    )
    assert yanit.status_code == 403


def test_uye_olmayan_uye_ekleyemez(rollu_gorev, yabanci_user, istemci_yap):
    yanit = istemci_yap(yabanci_user).post(
        reverse("mission-members", args=[rollu_gorev.id]),
        {"username": "sahip", "role": "owner"},
        format="json",
    )
    assert yanit.status_code == 404


def test_olmayan_kullanici_eklenemez(rollu_gorev, owner_user, istemci_yap):
    yanit = istemci_yap(owner_user).post(
        reverse("mission-members", args=[rollu_gorev.id]),
        {"username": "hic_boyle_biri_yok", "role": "viewer"},
        format="json",
    )
    assert yanit.status_code == 400


def test_ayni_kullanici_iki_kez_eklenemez(rollu_gorev, owner_user, operator_user, istemci_yap):
    yanit = istemci_yap(owner_user).post(
        reverse("mission-members", args=[rollu_gorev.id]),
        {"username": operator_user.username, "role": "viewer"},
        format="json",
    )
    assert yanit.status_code == 400


# --- Rol degisikligi ve son sahip korumasi -------------------------------


def test_owner_rol_degistirebilir(rollu_gorev, owner_user, viewer_user, istemci_yap):
    uyelik = MissionMember.objects.get(mission=rollu_gorev, user=viewer_user)
    yanit = istemci_yap(owner_user).patch(
        reverse("mission-member-detail", args=[rollu_gorev.id, uyelik.id]),
        {"role": "operator"},
        format="json",
    )

    assert yanit.status_code == 200
    uyelik.refresh_from_db()
    assert uyelik.role == MissionMember.Role.OPERATOR


def test_son_owner_rolu_dusurulemez(rollu_gorev, owner_user, istemci_yap):
    uyelik = MissionMember.objects.get(mission=rollu_gorev, user=owner_user)
    yanit = istemci_yap(owner_user).patch(
        reverse("mission-member-detail", args=[rollu_gorev.id, uyelik.id]),
        {"role": "viewer"},
        format="json",
    )

    assert yanit.status_code == 400
    uyelik.refresh_from_db()
    assert uyelik.role == MissionMember.Role.OWNER


def test_son_owner_cikarilamaz(rollu_gorev, owner_user, istemci_yap):
    uyelik = MissionMember.objects.get(mission=rollu_gorev, user=owner_user)
    yanit = istemci_yap(owner_user).delete(
        reverse("mission-member-detail", args=[rollu_gorev.id, uyelik.id])
    )

    assert yanit.status_code == 400
    assert MissionMember.objects.filter(pk=uyelik.pk).exists()


def test_ikinci_owner_varken_ilki_dusurulebilir(
    rollu_gorev, owner_user, operator_user, istemci_yap
):
    """Son sahip korumasi yalnizca SON sahibi korur, sahipligi dondurmaz."""
    ikinci = MissionMember.objects.get(mission=rollu_gorev, user=operator_user)
    ikinci.role = MissionMember.Role.OWNER
    ikinci.save(update_fields=["role"])

    ilk = MissionMember.objects.get(mission=rollu_gorev, user=owner_user)
    yanit = istemci_yap(owner_user).patch(
        reverse("mission-member-detail", args=[rollu_gorev.id, ilk.id]),
        {"role": "viewer"},
        format="json",
    )

    assert yanit.status_code == 200


def test_operator_rol_degistiremez(rollu_gorev, operator_user, viewer_user, istemci_yap):
    uyelik = MissionMember.objects.get(mission=rollu_gorev, user=viewer_user)
    yanit = istemci_yap(operator_user).patch(
        reverse("mission-member-detail", args=[rollu_gorev.id, uyelik.id]),
        {"role": "owner"},
        format="json",
    )
    assert yanit.status_code == 403


def test_baska_gorevin_uyeligi_bu_gorevden_degistirilemez(
    rollu_gorev, owner_user, other_user, istemci_yap
):
    """Kimlik tahminiyle baska gorevin uyeligine dokunulamamali."""
    baska = Mission.objects.create(name="Baska gorev", created_by=other_user)
    baska_uyelik = MissionMember.objects.get(mission=baska, user=other_user)

    yanit = istemci_yap(owner_user).patch(
        reverse("mission-member-detail", args=[rollu_gorev.id, baska_uyelik.id]),
        {"role": "viewer"},
        format="json",
    )
    assert yanit.status_code == 404


# --- Migration backfill ---------------------------------------------------


def test_backfill_migration_mevcut_sahipleri_tasiyor():
    """Backfill mantiginin kendisi: created_by'i olan gorev owner uyeligi alir.

    Migration'in kendisi uygulanmis durumda (test veritabani migrate edilerek
    kuruluyor); burada dogrulanan sey, ayni kuralin bugun de gecerli olmasi.
    """
    kullanici = User.objects.create_user(username="eski_sahip", password="x-parola-123")
    mission = Mission.objects.create(name="Eski gorev", created_by=kullanici)

    assert MissionMember.objects.filter(
        mission=mission, user=kullanici, role=MissionMember.Role.OWNER
    ).exists()
