"""Kok URL yapilandirmasi.

MEDIA DOSYALARI BURADAN SERVIS EDILMEZ.

Hafta 5'e kadar DEBUG acikken Django'nun static() yardimcisi /media/ altini
dogrudan sunuyordu. O yol KIMLIK DOGRULAMASIZDI: adresi bilen herkes, oturum
acmadan, herhangi bir gorevin goruntusunu indirebiliyordu. Hafta 6'da gorev
uyeligi devreye girince bu bir tutarsizliktan cikip acik bir bypass haline
geldi -- uyelik denetimini tamamen dolasiyordu.

Goruntulere erisimin TEK yolu artik /api/frames/{id}/image/ ucudur; o uc
Authorization basligini okur, karenin gorevine uyeligi dogrular ve dosya adini
istemciden degil veritabanindan alir.

Uretimde zaten media servis edilmiyordu; bu degisiklik gelistirme ortamini da
uretimle ayni davranisa getiriyor.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
]
