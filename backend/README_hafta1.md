# Gozcu API - Hafta 1

Uctan uca boru hattinin ilk halkasi: goruntu yuklenir, veritabanina kaydedilir,
listelenir. Bu adimda model calistirilmaz, tespit yapilmaz.

Yigin: Django 5.2.17 + Django REST Framework 3.18.1 + SimpleJWT 5.5.1,
PostgreSQL 16 + PostGIS 3.5, psycopg 3.3.5, Python 3.13 (slim-bookworm).

## 1. Sifirdan calistirma

Proje kokunde (`gozcu/`):

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # ciktiyi DJANGO_SECRET_KEY'e yaz
# .env icindeki POSTGRES_PASSWORD degerini de degistir
```

`DJANGO_SECRET_KEY` bos birakilirsa uygulama `ImproperlyConfigured` ile acilmaz;
kodda gizli bir varsayilan yoktur.

```bash
docker compose up -d --build
docker compose ps            # db "healthy", web "running" gorunmeli
```

Migration ve super kullanici (tek seferlik):

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Admin paneli: http://localhost:8000/admin/ (bes tablo da burada listelenir).

## 2. Saglik kontrolu

```bash
curl -i http://localhost:8000/api/health/
```

Beklenen: `200` ve `{"status":"ok","database":"ok"}`.
Veritabanina erisilemiyorsa `503` ve `{"status":"degraded","database":"error",...}`.

## 3. Token alma

```bash
curl -s -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"KULLANICI","password":"PAROLA"}'
```

Kolaylik icin token'i kabuk degiskenine al:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"KULLANICI","password":"PAROLA"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")
```

Suresi dolan access token'i yenilemek icin:

```bash
curl -s -X POST http://localhost:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"REFRESH_TOKEN"}'
```

## 4. Gorev olusturma ve listeleme

```bash
curl -s -X POST http://localhost:8000/api/missions/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Ornek gorev","description":"Hafta 1 denemesi"}'

curl -s http://localhost:8000/api/missions/ -H "Authorization: Bearer $TOKEN"
```

`created_by` istemciden alinmaz, oturum acan kullanici atanir; herkes yalnizca
kendi gorevlerini gorur.

## 5. Goruntu yukleme

Cok dosya tek istekte gonderilebilir (alan adi `images`):

```bash
curl -s -X POST http://localhost:8000/api/missions/1/frames/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "images=@/yol/foto1.jpg" \
  -F "images=@/yol/foto2.jpg"
```

Yanit `201` ve her dosya icin ayri sonuc:

```json
[{"id": 1, "filename": "foto1.jpg", "duplicate": false, "width": 4000, "height": 3000}]
```

- `width`/`height` istemciden degil, Pillow ile dosyadan okunur.
- SHA-256 ozet dosya parca parca okunarak hesaplanir.
- Ayni gorevde ayni ozet ikinci kez yuklenirse yeni kayit acilmaz, mevcut kayit
  `"duplicate": true` ile doner. Ayni dosya farkli gorevlere yuklenebilir.
- EXIF varsa cekim zamani ve GPS enlem/boylam/irtifa doldurulur; yoksa null kalir.
- Goruntu olmayan veya bozuk dosya `400` doner ve istegin tamami kaydedilmez.

Listeleme (sayfali, duruma gore filtrelenebilir):

```bash
curl -s "http://localhost:8000/api/missions/1/frames/?status=pending" \
  -H "Authorization: Bearer $TOKEN"
```

Gecerli durumlar: `pending`, `queued`, `processing`, `done`, `failed`.
Yeni yuklenen her kayit `pending` ile baslar.

## 6. Testler

Testler konteyner icinde calisir:

```bash
docker compose exec web pytest
```

Host'tan `pytest` calistirmayin: `DB_HOST=db` yalnizca compose agi icinde cozulur.

## 7. Uc listesi

| Yontem | Uc | Kimlik |
|---|---|---|
| GET | `/api/health/` | gerekmez |
| POST | `/api/auth/token/` | gerekmez |
| POST | `/api/auth/token/refresh/` | gerekmez |
| GET, POST | `/api/missions/` | gerekir |
| POST | `/api/missions/{id}/frames/` | gerekir |
| GET | `/api/missions/{id}/frames/` | gerekir |

## Bilinen kisit

Veritabani imaji olarak resmi `postgis/postgis:16-3.5` yerine
`imresamu/postgis:16-3.5` kullanildi: resmi imaj yalnizca amd64 yayinlanir ve
Apple Silicon'da `no matching manifest for linux/arm64/v8` hatasiyla duser;
`imresamu/postgis` docker-postgis bakimcilarindan birinin cok mimarili TEST
deposudur ve arm64 destegi DENEYSEL olarak isaretlidir. amd64 bir makinede
calisiliyorsa `docker-compose.yml` icindeki yorum satiri acilarak resmi imaja
donulebilir.

PostGIS eklentisi migration ile aktif edilmistir ancak bu adimda hicbir modelde
cografi alan (PointField vb.) yoktur; alanlar sonraki adimlarda eklenecektir.
