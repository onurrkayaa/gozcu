"""Gorev bazli erisim denetimi.

Tek kural: bir gorevin verisine YALNIZCA o gorevin uyeleri erisir. Bu kural
gorevin kendisi kadar altindaki her sey icin de gecerlidir -- kareler, kare
goruntu dosyalari, kosular, tespitler, incelemeler, bulgular ve denetim
kayitlari.

Erisimi olmayan kullaniciya 403 degil 404 doneriz. 403 "boyle bir kayit var
ama senin degil" bilgisini sizdirir; kimlik numarasi deneyerek baskasinin kac
gorevi oldugunu saymak mumkun hale gelir. 404 bu bilgiyi de vermez.

Yetki matrisi:

    islem                        owner  operator  viewer  uye degil
    gorevi gorme/listeleme         +       +        +        -
    kare ekleme                    +       +        -        -
    tarama baslatma                +       +        -        -
    inceleme yazma                 +       +        -        -
    bulgu yazma                    +       +        -        -
    kumeleme calistirma            +       +        -        -
    uye yonetimi                   +       -        -        -
    denetim kaydi okuma            +       +        +        -
    denetim kaydi yazma/degistirme -       -        -        -   (API ucu yok)
"""
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .models import Mission, MissionMember


def kullanicinin_gorevleri(user):
    """Kullanicinin UYE oldugu gorevler.

    Mission.created_by'a BAKMAZ: sahiplik bilgisi migration ile uyelik
    tablosuna tasindi ve tek yetki kaynagi orasi. Iki yerden birden okumak,
    uyelikten cikarilmis bir kullanicinin created_by uzerinden erisimi
    surdurmesi demek olurdu.
    """
    return Mission.objects.filter(members__user=user)


def uyelik_getir(user, mission_id):
    """Kullanicinin gorevdeki uyeligi; yoksa None."""
    if not user or not user.is_authenticated:
        return None
    return MissionMember.objects.filter(mission_id=mission_id, user=user).first()


def rol_getir(user, mission_id):
    uyelik = uyelik_getir(user, mission_id)
    return uyelik.role if uyelik else None


def gorevi_al_veya_404(user, mission_id, *, yazma=False, yonetim=False):
    """Gorevi uyelik denetiminden gecirerek getirir.

    yazma=True  -> owner veya operator gerekir
    yonetim=True -> owner gerekir

    Yetkisi olmayan UYE icin 403 doner -- gorevi zaten goruyor, 403 ona yeni
    bir bilgi vermiyor. Uye OLMAYAN icin 404 doner.
    """
    mission = get_object_or_404(Mission, pk=mission_id)
    uyelik = uyelik_getir(user, mission_id)
    if uyelik is None:
        # Uye degil: gorevin varligi bile sizmasin.
        raise Http404("Gorev bulunamadi.")

    if yonetim and uyelik.role not in MissionMember.ADMIN_ROLES:
        raise PermissionDenied("Bu islem icin gorev sahibi olmak gerekiyor.")
    if yazma and uyelik.role not in MissionMember.WRITE_ROLES:
        raise PermissionDenied("Bu gorevde salt okunur yetkiniz var.")

    return mission


class GorevUyesi(BasePermission):
    """View'in `get_mission_id()` dondurdugu goreve uyelik arar."""

    def has_permission(self, request, view):
        mission_id = view.get_mission_id()
        return uyelik_getir(request.user, mission_id) is not None
