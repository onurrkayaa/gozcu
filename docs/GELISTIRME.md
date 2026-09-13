# Geliştirme rehberi

Gözcü'yü çalıştırmak, geliştirmek ve test etmek için tek belge. Yalnızca sistemi
**görmek** istiyorsanız [DEMO.md](../DEMO.md) yeterlidir.

---

## 1. Mimari

```
Tarayıcı ──► nginx :8080 ──┬──► /          React SPA (derlenmiş)
                           └──► /api/      gunicorn ──► Django + DRF
                                                          │
                                     ┌────────────────────┼────────────────┐
                                     ▼                    ▼                ▼
                              PostgreSQL 16        Redis (kuyruk)     media/ (kareler)
                                + PostGIS                │
                                                         ▼
                                                  Celery worker
                                                         │
                                                  SAHI karolama
                                                         │
                                                  ONNX Runtime (Model-512)
```

Tarama isteği **anında dönmez**: `POST /api/missions/{id}/runs/` bir koşu kaydı
açar, `202` döner ve işi Celery kuyruğuna atar. 4000×3000 bir görüntünün
karolanarak taranması CPU'da ~30 saniye sürdüğü için bu iş HTTP isteğinin
dışına çıkarılmıştır. Arayüz ilerlemeyi `GET /api/runs/{id}/` ile yoklar.

| Katman | Teknoloji | Neden |
|---|---|---|
| API | Django 5.2 + DRF | Hazır kimlik doğrulama, yetkilendirme, admin; GeoDjango ile PostGIS |
| Veritabanı | PostgreSQL 16 + PostGIS | Coğrafi sorgular ve metre tabanlı mesafe hesabı veritabanında |
| Kuyruk | Celery + Redis | Uzun tarama isteği bloke etmesin; işçi ölürse iş kaybolmasın |
| Çıkarım | ONNX Runtime | PyTorch'suz, hafif ve taşınabilir çalışma zamanı |
| Karolama | SAHI | 4000×3000 görüntüyü 512 px karolara böler, sonuçları birleştirir |
| Arayüz | React 19 + TypeScript + Vite | Tip güvenliği; TanStack Query ile sunucu durumu |
| Harita | Leaflet + react-leaflet | Hafif, açık kaynak, ek hesap gerektirmez |

## 2. Kurulum

### 2.1. Sistem gereksinimleri

- Docker Desktop (backend, veritabanı, kuyruk için)
- Node.js 20+ (arayüzü geliştirme modunda çalıştırmak için; Node 24.20 ile geliştirildi)
- Python 3.13 (yalnızca `scripts/` altındaki ölçüm kodunu çalıştıracaksanız)

### 2.2. Ortam dosyası

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # POSTGRES_PASSWORD
```

`DJANGO_SECRET_KEY` boş bırakılırsa uygulama `ImproperlyConfigured` ile açılmaz;
kodda gizli bir varsayılan **yoktur**. Her değişkenin anlamı `.env.example`
içinde yazılıdır.

### 2.3. Geliştirme yığını

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
cd frontend && npm install && npm run dev
```

| Adres | Ne |
|---|---|
| <http://localhost:5173> | Arayüz (Vite, sıcak yeniden yükleme) |
| <http://localhost:8000/api/> | API (doğrudan) |
| <http://localhost:8000/admin/> | Django admin |

Geliştirme override'ı şunları değiştirir: kod host'tan bağlanır (`runserver`
otomatik yeniden yükler), 8000 portu dışarı açılır, `DJANGO_DEBUG=1` olur,
arayüz konteyneri çalışmaz. Vite proxy'si `/api` isteklerini 8000'e yollar;
bu sayede tarayıcı aynı kaynaktan konuşur ve CORS ayarı gerekmez.

### 2.4. Üretim benzeri yığın

```bash
docker compose up -d     # gunicorn + nginx + derlenmiş arayüz
```

Tek adres: <http://localhost:8080>. Farkları için bkz. bölüm 6.

### 2.5. Yönetici hesabı

```bash
docker compose exec web python manage.py createsuperuser
```

## 3. Komutlar

### Backend

| Komut | Ne yapar |
|---|---|
| `docker compose exec web pytest -q` | Backend testleri |
| `docker compose exec web python manage.py migrate` | Şema |
| `docker compose exec web python manage.py makemigrations --check --dry-run` | Eksik migration var mı |
| `docker compose exec web python manage.py check --deploy` | Dağıtım denetimi |
| `docker compose exec web python manage.py demo_kur` | Uçtan uca demo verisi |
| `docker compose exec web python manage.py demo_konum_uret --kullanici <ad>` | Yalnızca harita için demo konumları |
| `docker compose logs -f worker` | Celery işçi günlüğü |

### Arayüz (`frontend/`)

| Komut | Ne yapar |
|---|---|
| `npm run dev` | Geliştirme sunucusu (5173) |
| `npm test` | Vitest |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript |
| `npm run build` | Üretim derlemesi |
| `npm run etiketleme` | Kör etiketleme aracı (araştırma, Bölüm 8) |

### Ölçüm script'leri (`scripts/`)

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest scripts/tests tests -q
```

Script'lerin tamamı HERIDAL veri kümesini `data/heridal/` altında bekler; veri
kümesi depoda **yoktur**. Hangi script'in hangi CSV'yi ürettiği
[reports/README.md](../reports/README.md) içinde listelidir.

Yalnızca testleri çalıştıracaksanız `requirements-test.txt` yeterlidir; PyTorch
ve ultralytics gerekmez.

### Depo denetimi

```bash
python3 scripts/depo_denetimi.py
```

İzlenen dosyalarda sır, model ağırlığı, `node_modules`, `dist`, yerel mutlak yol
ve beklenmedik büyük dosya arar. CI'da kapı olarak koşar.

## 4. Dizin düzeni

```
gozcu/
├── backend/            Django + DRF + Celery
│   ├── core/           models, views, serializers, tasks, tiling, detector
│   │   ├── demo.py     demo verisi üretimi (iki komut da bunu kullanır)
│   │   ├── kumeleme.py Union-Find ile coğrafi kümeleme
│   │   ├── yetki.py    görev üyeliğine dayalı erişim
│   │   └── denetim.py  denetim kaydı yazma
│   └── tests/          235 test
├── frontend/           React + TypeScript + Vite
│   ├── src/sayfalar/   sayfa bileşenleri
│   ├── src/bilesenler/ harita, tespit katmanı, inceleme paneli
│   ├── src/kimlik/     JWT oturumu
│   ├── arastirma/      kör etiketleme aracı (Bölüm 8)
│   └── nginx.conf      üretim benzeri servis + API vekili
├── scripts/            ölçüm ve analiz script'leri (numaralı, sırayla)
│   └── tests/          217 test
├── reports/            ölçüm çıktıları (CSV) — rapordaki her sayının kaynağı
├── rapor/              Türkçe rapor: bolum_01..08 + birleşik belge
├── docs/               bu rehber ve güvenlik modeli
├── agirliklar/         model ağırlıkları (Git'te YOK)
├── data/               HERIDAL veri kümesi (Git'te YOK)
├── docker-compose.yml  üretim benzeri yığın
├── docker-compose.dev.yml  geliştirme override'ı
└── demo.sh             tek komutluk demo
```

## 5. Tasarım kararları

Aşağıdakiler rapordaki gerekçelerin kısa özetidir; ayrıntıları ilgili bölümlerde.

### 5.1. Güven eşiği veriye pişirilmez

Tespitler sabit bir **0,05 tabanıyla** kaydedilir (`DETECTION_STORE_FLOOR`),
koşunun `conf_threshold` değeri kayda karışmaz. Bir tam tarama pahalıdır; tek
koşudan her eşiği sorabilmek için eşik **okuma anında** uygulanır. Arayüzdeki
kaydırıcı bu yüzden modeli yeniden çalıştırmaz.

### 5.2. `acks_late` ve idempotanslık birbirine bağlı

Celery mesajı görev **bittikten sonra** onaylar: işçi iş ortasında ölürse mesaj
kaybolmaz, yeniden dağıtılır. Bedeli, görevin iki kez çalışabilmesidir — bu
yüzden `process_frame` içindeki "önce sil, sonra yaz" idempotansliği
zorunludur. İkisi ayrı ayrı düşünülemez.

### 5.3. Operatör kararı model çıktısına dokunmaz

`Review` ayrı bir tablodur. Aynı alana yazılsalardı modelin ne bulduğu ile
operatörün ne düşündüğü geri dönülmez biçimde karışır ve geçmiş ölçümler yeniden
üretilemezdi. Tekillik (tespit, inceleyen) çiftindedir: iki operatörün
anlaşamadığı bilgisi korunur.

### 5.4. Arayüz koordinat üretmez

`scripts/22_konum_kaynagi_tara.py` ile veri kümesinin tamamı (1579 görüntü)
tarandı: **hiçbirinde EXIF GPS yok**. Kayıtta gerçek koordinat varsa gösterilir
ve kaynağı yazılır; yoksa "Konum bilgisi mevcut değil" denir. Dosya sırasından,
karo satır/sütunundan veya görüntü pikselinden enlem/boylam **türetilmez** —
böyle bir değer ölçüm değil uydurma olur ve bir arama ekibini yanlış noktaya
yönlendirir.

### 5.5. Gerçek dedektör yüklenemezse sessizce sahteye düşülmez

`get_detector()` seçimi `ModelVersion.framework` alanına bakar. `onnx` olan bir
koşuda model yüklenemezse hata yükselir ve kare `failed` olur. Sessizce
`fake-v0`'a düşmek, model bozukken sistemin "çalışıyor" görünmesi demektir.

### 5.6. Küme merkezi ölçülmüş bir konum değildir

Üyelerin aritmetik ortalamasıdır; orada gerçekten bir şey bulunduğu anlamına
gelmez. 50 metre kümeleme eşiği de bir **karardır**, ölçülmüş bir değer değil:
gerçek uçuş verisi olmadığı için hangi eşiğin doğru olduğu ölçülemedi.

### 5.7. `/media/` kapalıdır

Görüntüye erişimin tek yolu `/api/frames/{id}/image/` ucudur; o uç
`Authorization` başlığını okur, karenin görevine üyeliği doğrular ve dosya adını
istemciden değil veritabanından alır. Ayrıntı: [GUVENLIK.md](GUVENLIK.md).

## 6. Geliştirme ve üretim benzeri farkı

| | Geliştirme | Üretim benzeri |
|---|---|---|
| Compose | `-f docker-compose.yml -f docker-compose.dev.yml` | `docker-compose.yml` |
| Django | `runserver`, kod host'tan bağlı | `gunicorn`, kod imajda |
| Arayüz | `npm run dev` (Vite, 5173) | nginx + derlenmiş dosyalar (8080) |
| `DEBUG` | 1 | 0 |
| CORS | tüm kaynaklara açık | yalnızca açık liste |
| Statik dosyalar | Django | whitenoise + nginx |
| Dış portlar | 8000 (API) + 5173 (arayüz) | yalnızca 127.0.0.1:8080 |
| PostgreSQL / Redis | yayınlanmaz | yayınlanmaz |

**TLS hiçbirinde yoktur.** Gerçek bir dağıtımda HTTPS'i önde duran bir ters
vekil sonlandırmalı ve `DJANGO_HTTPS=1` verilmelidir.

## 7. Sürekli entegrasyon

`.github/workflows/` altında beş iş akışı:

| İş akışı | Ne çalışır | Yerel karşılığı |
|---|---|---|
| `backend.yml` | migration denetimi, `check --deploy`, pytest (PostGIS + Redis servisleriyle) | `docker compose exec web pytest -q` |
| `frontend.yml` | lint, TypeScript, Vitest, üretim derlemesi | `npm run lint && npm run typecheck && npm test && npm run build` |
| `scriptler.yml` | analiz script'lerinin testleri (veri kümesi ve ağırlık olmadan) | `.venv/bin/python -m pytest scripts/tests tests -q` |
| `depo.yml` | sır, artifact, yerel yol ve büyük dosya taraması + geçmiş taraması | `python3 scripts/depo_denetimi.py` |
| `dagitim.yml` | üretim benzeri yığını kurar, sağlık/`/media/`/port/demo/kalıcılık kontrolleri | `./demo.sh` |

Veri kümesi ve model ağırlıkları CI'ya **indirilmez**; model gerektiren
davranışlar sahte oturumla sınanır. "Atlayarak yeşil" yaklaşımı kullanılmaz.

## 8. Model dosyası

`agirliklar/model512_best.onnx` depoda **yoktur** (10,5 MB ikili; lisans ve boyut
kararı). Elinizde varsa `agirliklar/` klasörüne koyun; compose onu `/models`
altına salt okunur bağlar.

Beklenen kimlik (`reports/model512_onnx_bilgisi.csv`):

| Alan | Değer |
|---|---|
| ONNX SHA-256 | `361731351703f4581f95871c26583eba760f08ed26493869cc864c8c57f55dbd` |
| Kaynak `.pt` SHA-256 | `66a93278a16e1cf720052dbde975f9c5b13ab3881e2416dd1bd78d6815fdf3b7` |
| Girdi | `images: 1x3x512x512`, opset 18 |
| Çıktı | `output0: 1x5x5376`, sınıf `0:human` |

Doğrulama:

```bash
shasum -a 256 agirliklar/model512_best.onnx
```

Dosya yoksa `fake-v0` ile çalışan demo ve testler çalışmaya devam eder; `onnx`
sürümüyle başlatılan koşular açık hatayla `failed` olur.

## 9. Bilinen kısıtlar

- Tarama iptali veya yeniden başlatma ucu yok; arayüz uydurma düğme göstermez.
- Listeler ilk sayfayla sınırlı (20 kayıt); toplam sayı ayrıca yazılır.
- Arayüzde kullanıcı arama yok; üye eklerken kullanıcı adı elle yazılır.
- Bulgu durumu ve başlığı API'den düzenlenebilir, arayüze bağlanmadı.
- Kümeleme elle tetiklenir; yeni bulgu eklendiğinde kendiliğinden hesaplanmaz.
- Uçtan uca tarayıcı test paketi (Playwright vb.) kurulmadı; tarayıcı
  doğrulaması elle yürütüldü ve ölçüm kayıtlarına yazıldı.
- Güvenlik sınırları: [GUVENLIK.md](GUVENLIK.md).
