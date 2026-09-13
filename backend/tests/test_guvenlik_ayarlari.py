"""Uretim benzeri guvenlik ayarlarinin davranis testleri.

Burada olculen sey ayarlarin DEGERI degil, ETKISIDIR: bir ayar dosyasinda
dogru yazip yanlis yerde ezmek mumkun; bu testler gercek bir istek-yanit
uzerinden bakar.

Bu testlerin gecmesi tum saldirilarin engellendigi anlamina GELMEZ.
"""
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.fixture(autouse=True)
def throttle_onbellegini_temizle():
    """Hiz siniri sayaci testler arasinda tasinmasin.

    DRF sayaci Django onbelleginde tutar; onbellek surec boyunca yasadigi icin
    temizlenmezse bir testin istekleri digerinin butcesini tuketir."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


class TestGuvenlikBasliklari:
    def test_icerik_turu_tahmini_kapali(self, client):
        yanit = client.get(reverse("health"))
        assert yanit.headers["X-Content-Type-Options"] == "nosniff"

    def test_cerceveye_gomulemez(self, client):
        yanit = client.get(reverse("health"))
        assert yanit.headers["X-Frame-Options"] == "DENY"

    def test_referrer_politikasi_ayni_kaynak(self, client):
        yanit = client.get(reverse("health"))
        assert yanit.headers["Referrer-Policy"] == "same-origin"


class TestCors:
    def test_debug_kapaliyken_joker_kaynak_yok(self, settings):
        """CORS_ALLOW_ALL_ORIGINS yalnizca DEBUG'a bagli olmali.

        Uretimde joker acik kalirsa herhangi bir site kullanicinin tarayicisi
        uzerinden API'yi cagirabilir."""
        from django.conf import settings as canli

        if not canli.DEBUG:
            assert canli.CORS_ALLOW_ALL_ORIGINS is False
        assert "*" not in canli.CORS_ALLOWED_ORIGINS


class TestGirisHizSiniri:
    """Giris ucu kendi dar kovasinda; kaba kuvvet denemesi yavaslatilir.

    Deger bir KARARDIR (varsayilan 10/dk), olculmus bir esik degildir ve tek
    basina kaba kuvveti ENGELLEMEZ."""

    def test_yanlis_parola_denemesi_bir_noktada_kisitlaniyor(self, client, user):
        """Yapilandirilmis butce kadar deneme yapilir, bir fazlasi reddedilir.

        Esik AYARDAN okunur, teste sabit yazilmaz: ayar degistiginde test
        kendiliginde ona uyar ve "ayarda bir sey yaziyor ama etkisi yok"
        durumu yakalanir."""
        from django.conf import settings as canli

        butce = int(canli.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["giris"].split("/")[0])
        url = reverse("token_obtain_pair")
        kodlar = [
            client.post(url, {"username": "onur", "password": "yanlis"}).status_code
            for _ in range(butce + 1)
        ]
        assert kodlar[-1] == status.HTTP_429_TOO_MANY_REQUESTS, kodlar
        assert kodlar[0] == status.HTTP_401_UNAUTHORIZED, kodlar

    def test_dogru_parola_makul_sayida_denemede_calisiyor(self, client, user):
        url = reverse("token_obtain_pair")
        yanit = client.post(
            url, {"username": "onur", "password": "gizli-parola-123"}
        )
        assert yanit.status_code == status.HTTP_200_OK
        assert "access" in yanit.json()
        assert "refresh" in yanit.json()

    def test_token_yanitta_doner_url_de_gecmez(self, client, user):
        """Belirtec yalnizca govdede doner; adres satirina veya log'a girmez."""
        url = reverse("token_obtain_pair")
        yanit = client.post(url, {"username": "onur", "password": "gizli-parola-123"})
        assert "access" not in yanit.headers.get("Location", "")
        assert yanit.json()["access"] not in url


class TestOturumSuresi:
    def test_erisim_belirteci_yenilemeden_kisa_omurlu(self):
        from django.conf import settings as canli

        erisim = canli.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
        yenileme = canli.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
        assert erisim < yenileme
        # Cok uzun bir erisim belirteci, iptal mekanizmasi olmadigi icin
        # calindiginda uzun sure gecerli kalir demektir.
        assert erisim.total_seconds() <= 60 * 60
