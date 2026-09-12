"""Denetim kaydi yazma yardimcilari.

Iki kural buradaki her seyi belirliyor:

1. BASARISIZ ISLEM DENETIM KAYDI URETMEZ. Kayit, islemi yapan kodla AYNI
   veritabani islemi icinde yazilir; islem geri alinirsa kayit da geri alinir.
   Aksi halde denetim gecmisi olmamis seyleri anlatir ve guvenilmez hale gelir.

2. HAM NESNE DOKULMEZ. `changes` alanina yalnizca degisen alanlarin ozeti
   yazilir ve hassas anahtarlar temizlenir. Parola, token, oturum anahtari,
   dosya icerigi ve gereksiz kisisel veri bu tabloya girmez.
"""
import logging

from .models import AuditLog

logger = logging.getLogger(__name__)

#: Bu alt dizeleri iceren anahtarlar denetim kaydina YAZILMAZ. Liste
#: genisletilebilir; eksik kalirsa tek bedeli bir alanin maskelenmemesi olur,
#: bu yuzden supheli olan anahtari eklemek her zaman dogru taraftir.
HASSAS_ANAHTARLAR = (
    "password", "parola", "token", "secret", "sifre", "key", "authorization",
    "session", "cookie", "csrf", "email", "e_posta", "refresh", "access",
)

#: Tek bir alan degeri icin ust sinir. Uzun metinler (not alanlari) denetim
#: tablosunu sismekten korunur; tam metin zaten kaydin kendisinde durur.
DEGER_SINIRI = 200


def _hassas_mi(anahtar):
    ad = str(anahtar).lower()
    return any(parca in ad for parca in HASSAS_ANAHTARLAR)


def _degeri_sadelestir(deger):
    """Degeri JSON'a yazilabilir, sinirli bir bicime indirger."""
    if deger is None or isinstance(deger, (bool, int, float)):
        return deger
    metin = str(deger)
    if len(metin) > DEGER_SINIRI:
        return metin[:DEGER_SINIRI] + "…"
    return metin


def degisiklik_ozeti(onceki=None, sonraki=None):
    """Onceki/sonraki sozluklerinden guvenli bir ozet uretir.

    Yalnizca GERCEKTEN degisen alanlar yazilir: degismeyen alanlari da yazmak
    kaydi buyutur ve neyin degistigini okumayi zorlastirir.
    """
    onceki = onceki or {}
    sonraki = sonraki or {}
    ozet = {}
    for anahtar in sorted(set(onceki) | set(sonraki)):
        if _hassas_mi(anahtar):
            continue
        eski = onceki.get(anahtar)
        yeni = sonraki.get(anahtar)
        if eski == yeni:
            continue
        ozet[str(anahtar)] = {
            "onceki": _degeri_sadelestir(eski),
            "sonraki": _degeri_sadelestir(yeni),
        }
    return ozet


def denetim_yaz(*, actor, mission, action, nesne=None, object_type="", object_id="",
                onceki=None, sonraki=None, ek=None):
    """Denetim kaydi olusturur.

    Cagiran kodun ISLEMIYLE AYNI transaction icinde calistirilmalidir; bu
    fonksiyon kendi basina transaction acmaz, boylece disaridaki islem geri
    alinirsa kayit da geri alinir.
    """
    if nesne is not None:
        object_type = object_type or nesne.__class__.__name__
        object_id = object_id or str(getattr(nesne, "pk", ""))

    changes = degisiklik_ozeti(onceki, sonraki)
    if ek:
        for anahtar, deger in ek.items():
            if not _hassas_mi(anahtar):
                changes[str(anahtar)] = _degeri_sadelestir(deger)

    return AuditLog.objects.create(
        actor=actor if (actor and actor.is_authenticated) else None,
        mission=mission,
        action=action,
        object_type=object_type,
        object_id=str(object_id or ""),
        changes=changes,
    )
