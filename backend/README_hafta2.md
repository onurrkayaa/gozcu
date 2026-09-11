# Hafta 2 -- Asenkron tarama boru hatti

Operator "taramayi baslat" der, is arka planda kuyruga girer, ilerleme takip
edilebilir. **Bu haftada gercek model yok**: yerine sahte bir dedektor calisiyor.
Amac boru hattinin dogrulugunu modelin yavasligindan bagimsiz dogrulamak.

Hafta 1'in uzerine eklenir, hicbir seyini degistirmez.

## Ne eklendi

| Parca | Dosya |
|---|---|
| Celery uygulamasi | `gozcu_api/celery.py` |
| Karolama ve kutu geometrisi (saf fonksiyonlar) | `core/tiling.py` |
| Dedektor arayuzu + sahte dedektor | `core/detector.py` |
| Celery gorevleri | `core/tasks.py` |
| Uclar | `core/views.py`, `core/urls.py`, `core/serializers.py` |
| `fake-v0` model kaydi | `core/migrations/0003_fake_model_version.py` |
| Testler | `tests/test_tiling.py`, `tests/test_runs.py` |

Servisler: `db`, `redis`, `web`, `worker`.

- Redis imaji `redis:8.10.1-alpine` -- etiket yama surumune kadar sabit,
  `latest` kullanilmiyor. arm64 destegi `docker image inspect` ile dogrulandi
  (Apple Silicon).
- `worker`, `web` ile **ayni imajdan** build edilir: ayni kod, ayni bagimliliklar,
  ayri surec.

## Sifirdan calistirma

```bash
# 1. Ortam dosyasi
cp .env.example .env
# DJANGO_SECRET_KEY uret ve .env'e yaz:
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# 2. Dort servisi ayaga kaldir
docker compose up -d --build

# 3. Veritabani semasi + fake-v0 model kaydi
docker compose exec web python manage.py migrate

# 4. Bir operator hesabi
docker compose exec web python manage.py createsuperuser
```

Durum kontrolu:

```bash
docker compose ps                 # dort servis de "healthy" / "running" olmali
docker compose logs -f worker     # isci "celery@... ready." demeli
curl -s http://localhost:8000/api/health/
```

Worker'i tek basina yeniden baslatmak:

```bash
docker compose restart worker
```

Konteyner disinda, elle calistirmak istersen (Redis ve Postgres ayakta olmali,
`.env` icindeki `redis` / `db` adlarini `localhost` yapmayi unutma):

```bash
cd backend
celery -A gozcu_api worker --loglevel=info --concurrency=2
```

## Testler

```bash
docker compose exec web pytest
```

`tests/test_tiling.py` veritabanina hic dokunmaz -- saf fonksiyonlar, milisaniyeler.
`tests/test_runs.py` gorevleri `CELERY_TASK_ALWAYS_EAGER` ile senkron kosturur:
Redis veya ayakta bir isci gerekmez, ama `tasks.py`'nin gercek kodu calisir.

## Ornek akis -- kopyala yapistir

Asagidaki blok bastan sona calisir. `jq` gerekmiyor, `python3` yeterli.

```bash
API=http://localhost:8000/api
KULLANICI=operator
PAROLA=parolan-burada

# --- 1. Token al -------------------------------------------------------------
TOKEN=$(curl -s -X POST $API/auth/token/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$KULLANICI\",\"password\":\"$PAROLA\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access'])")

# --- 2. Gorev olustur --------------------------------------------------------
MISSION=$(curl -s -X POST $API/missions/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Ornek arama","description":"Hafta 2 denemesi"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "gorev: $MISSION"

# --- 3. Goruntu yukle (birden fazla dosya tek istekte) -----------------------
curl -s -X POST $API/missions/$MISSION/frames/ \
  -H "Authorization: Bearer $TOKEN" \
  -F images=@/yol/kare0.jpg \
  -F images=@/yol/kare1.jpg

# --- 4. Model surumunu ogren -------------------------------------------------
MV=$(curl -s $API/models/ -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['results'][0]['id'])")

# --- 5. Taramayi baslat (202 doner, is arka planda) --------------------------
RUN=$(curl -s -X POST $API/missions/$MISSION/runs/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"model_version_id\":$MV,\"conf_threshold\":0.25,\"iou_threshold\":0.45,\"tile_size\":512,\"overlap_ratio\":0.2}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['run_id'])")
echo "kosu: $RUN"

# --- 6. Ilerlemeyi sor -------------------------------------------------------
curl -s $API/runs/$RUN/ -H "Authorization: Bearer $TOKEN"
# bitene kadar bekle:
until curl -s $API/runs/$RUN/ -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json;sys.exit(0 if json.load(sys.stdin)['status']=='done' else 1)"
do sleep 1; done
echo "tarama bitti"

# --- 7. Tespitleri listele (skora gore azalan, sayfali) ----------------------
curl -s "$API/runs/$RUN/detections/" -H "Authorization: Bearer $TOKEN"

# ayni kosudan farkli esik -- YENIDEN TARAMA YOK:
curl -s "$API/runs/$RUN/detections/?min_score=0.05" -H "Authorization: Bearer $TOKEN"

# tek bir kareyle sinirla:
curl -s "$API/runs/$RUN/detections/?frame_id=1" -H "Authorization: Bearer $TOKEN"
```

Gozlenen: 4000x3000 olcusunde **5 kare** (kare basina 80 karo, toplam 400 karo)
sahte dedektorle **6 saniyede** bitti.

## Uclar

| Uc | Ne yapar |
|---|---|
| `POST /api/missions/{id}/runs/` | Taramayi baslatir. `202` + `run_id`. Gorevde kare yoksa `400`. |
| `GET /api/runs/{id}/` | Durum, `frames_total` / `frames_done` / `frames_failed`, baslangic-bitis. |
| `GET /api/runs/{id}/detections/` | Skora gore azalan, sayfali. `min_score` ve `frame_id` ile filtrelenir. |
| `GET /api/models/` | `ModelVersion` listesi. |

Hepsi kimlik dogrulama ister. Sahiplik queryset seviyesinde suzulur: baskasinin
gorevi veya kosusu **404** doner -- "var ama yetkin yok" bilgisi bile sizmaz.

## Guven esigi neden kayda pisirilmiyor

Bu, bilincli bir tasarim karari ve projenin en onemli ayrimlarindan biri.

Dedektor ciktisi kaydedilirken kosunun `conf_threshold` degeri **filtre olarak
kullanilmaz**. Kutulardan yalnizca `settings.DETECTION_STORE_FLOOR` (0,05)
tabaninin altinda kalanlar atilir; NMS bundan sonra uygulanir. `conf_threshold`
yine de `InferenceRun` kaydina **yazilir** -- kosunun hangi niyetle baslatildigi
belli olsun diye -- ama kutulari kaydederken hicbir sey elemez.

Filtre **okuma aninda** uygulanir: `GET /api/runs/{id}/detections/` varsayilan
olarak o kosunun `conf_threshold` degerini uygular, istemci `min_score` verirse
onu uygular.

Sebep sure: gercek modelle bir tam tarama yaklasik **2 saat 40 dakika** suruyor.
Esik kayda pisirilseydi "0,15'te ne olurdu?" sorusu ancak bastan yeniden
tarayarak cevaplanabilirdi. Bu ayrimla tek bir pahali kosudan **her** esik icin
sonuc alinabiliyor; esik degistirmek bir sorgu parametresi, yeni bir tarama
degil.

## acks_late ve idempotanslik birbirine bagli

`settings.py`'de:

```python
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 900}
```

`acks_late` acik oldugu icin mesaj, gorev **bittikten sonra** onaylanir. Isci is
ortasinda oldurulurse mesaj kaybolmaz; Redis `visibility_timeout` dolunca onu
baska bir isciye yeniden dagitir. Varsayilan (erken onay) davranisinda mesaj
kaybolur, kare sonsuza kadar `processing` durumunda asili kalir ve chord hicbir
zaman tamamlanmaz -- kosu da hic `done` olmaz.

**Bedeli:** bir gorev iki kez calisabilir. Bu yuzden `core/tasks.py`'deki
sil-sonra-yaz idempotanslik bir suslemi degil, bu ayarin **zorunlu esi**.
Birini acip digerini kapatmak bozuk bir sistem verir:

- `acks_late` acik + idempotanslik yok -> tespitler ikiye katlanir.
- `acks_late` kapali + idempotanslik var -> isci olunce is sessizce kaybolur.

`visibility_timeout` 900 saniye, hard time limit (`CELERY_TASK_TIME_LIMIT = 660`)
degerinin rahatca uzerinde secildi. Boylece **hala calisan** bir gorev asla
"olmus" sayilip ikinci kez dagitilmaz; yeniden dagitim yalnizca isci gercekten
oldugunde devreye girer.

## Uc soru

**Gorevler nasil idempotent?** `process_frame` once `select_for_update()` ile
kareyi kilitler; kare zaten `done` ise dedektoru hic calistirmadan doner. Is
yapacaksa, yazmadan hemen once o `(kosu, kare)` ciftinin mevcut `Detection`
satirlarini **siler**, sonra `bulk_create` eder -- yani ikinci calisma ekleme
degil **yerine koyma** olur. `frames_done` artisi da ayni islemin icinde ve
yalnizca gercek `done` gecisine bagli, `F()` ifadesiyle atomik.

**Iki isci ayni kareyi almaya calisirsa?** `select_for_update()` Postgres'te
satir kilidi alir. Ikinci isci birincinin `COMMIT`'ine kadar bloke olur, sonra
satiri **yeniden okur**, `done` gorur ve is yapmadan doner. Dedektor iki kez
calismaz, sayac iki kez artmaz. Agir dedektor isi bilerek kilidin **disinda**
yapilir; kilit yalnizca durum okuma ve yazma anlarinda tutulur.

**Bir kare basarisiz olursa tarama neden yine `done`?** Cunku boru hatti sonuna
kadar isledi ve basarili karelerin tespitleri operator icin **kullanilabilir
durumda**. 200 karelik bir taramada 1 kare patladi diye kosunun tamamini
`failed` isaretlemek, calisan 199 karenin sonucunu gizlerdi -- operator arama
kurtarmada bunlara bakmak zorunda. Kismi basarisizlik kaybolmuyor, `frames_failed`
sayacinda gorunur kaliyor. `failed` durumu kosunun **kendisinin** cokmesine
ayrildi. Teknik tarafi: `process_frame` deneme hakki bitince istisnayi chord'un
disina tasirmaz, kareyi `failed` isaretleyip normal doner -- aksi halde chord
geri cagirmasi (`finalize_run`) hic calismaz ve kosu sonsuza kadar `running`
kalirdi.
