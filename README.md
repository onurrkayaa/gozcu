# Gözcü

Operator-support prototype for detecting people in aerial search-and-rescue
imagery. Undergraduate graduation project — research and education only.

**Language:** English below, [Türkçe aşağıda](#türkçe).

---

## What this is

Aerial search-and-rescue photographs are large (4000×3000 px) while the people in
them are small — a median annotated box of 60×59 px, about 0.03% of the image area.
Passing such an image straight to a detector downscales it to the model's 640 px
input, shrinking the median target to below 10 px across.

Gözcü scans each image as 512 px tiles with 20% overlap (via SAHI) so targets keep
their original scale, and presents the results to a human operator for review. The
backend is a Django + PostGIS service that stores missions, frames and detections.

## What this is **not**

- **Not** a deployed, certified or operationally validated system.
- **No** claim of clinical, emergency-response or operational fitness is made.
- It does **not** replace human search teams or any established SAR procedure.
- It is a student prototype whose measured accuracy (below) is far from
  anything that could be relied upon.

Every output is intended for review by a human operator.

## Measured baseline

No model has been trained yet. The figures below measure an off-the-shelf
COCO-pretrained detector (Ultralytics `yolo11n`) run with tiling, on CPU, to
establish a starting point. Matching uses IoU ≥ 0.3 at confidence threshold 0.30.

| Scope | Images | Boxes | Recall | FP / image |
|---|---:|---:|---:|---:|
| Full dataset | 1579 | 3073 | 0.3160 | 0.89 |
| Excluding dominant source (ZRI) | 1453 | 1776 | **0.2663** | **0.74** |

The dataset's 17 capture sources are very unevenly distributed; a single source
(ZRI) holds 42% of all annotations, so the ZRI-excluded row is the more
representative figure. Rerunning the measurement reproduced every cell of the
result table exactly.

All numbers in this README come from committed measurement scripts; nothing here
is estimated. Raw outputs live in `reports/`, and each CSV carries the exact run
conditions (model, parameters, library versions, date, command) in its `kosu_`
columns.

## Dataset

[HERIDAL](http://ipsar.fesb.unist.hr/HERIDAL%20database.html) — aerial human
detection dataset for search and rescue.

> Božić-Štulić, D., Marušić, Ž., Gotovac, S. (2019). *Deep Learning Approach in
> Aerial Imagery for Supporting Land Search and Rescue Missions.* International
> Journal of Computer Vision, 127, 1256–1278.

Accessed through a Roboflow Universe mirror distributed under **CC BY 4.0**. The
dataset is **not** included in this repository; `data/` is gitignored. Image
resolution was verified from the files rather than assumed.

## Running it

Requires Docker and Docker Compose.

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # write into DJANGO_SECRET_KEY
# also change POSTGRES_PASSWORD in .env
```

`DJANGO_SECRET_KEY` has no hidden default — the application refuses to start if it
is empty.

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
curl -i http://localhost:8000/api/health/     # expect 200 {"status":"ok","database":"ok"}
```

Admin panel: <http://localhost:8000/admin/>. Details in `backend/README_hafta1.md`.

The measurement scripts run outside Docker against a local dataset copy; see
`README_hafta0.md`.

## Layout

```
gozcu/
├── backend/           Django + DRF service (missions, frames, detections)
├── scripts/           measurement and analysis scripts (no training yet)
├── reports/           generated CSV/PNG outputs — gitignored
├── rapor/             project report chapters (Turkish)
├── data/              HERIDAL dataset — gitignored, not distributed
├── tests/             IoU and matching tests
└── docker-compose.yml
```

## License

**AGPL-3.0.** This project uses Ultralytics YOLO, which is licensed under
AGPL-3.0; as a public derivative work this repository carries the same license.
See [LICENSE](LICENSE). The HERIDAL dataset keeps its own CC BY 4.0 terms and is
not redistributed here.

---

# Türkçe

Havadan çekilmiş arama-kurtarma görüntülerinde insan tespiti için **operatör
destek prototipi**. Lisans bitirme projesi — yalnızca araştırma ve eğitim amaçlı.

## Bu proje nedir

Arama-kurtarma görüntüleri büyüktür (4000×3000 px), aranan insanlar ise küçüktür:
etiket kutusunun medyanı 60×59 px, yani görüntü alanının yaklaşık %0,03'ü. Böyle
bir görüntü doğrudan bir modele verildiğinde modelin 640 px'lik girişine küçültülür
ve medyan hedef 10 pikselin altına iner.

Gözcü her görüntüyü %20 örtüşmeli 512 px karolar hâlinde tarar (SAHI ile), böylece
hedefler kendi ölçeğini korur; sonuçlar bir insan operatörün incelemesine sunulur.
Arka uç, görevleri/kareleri/tespitleri saklayan bir Django + PostGIS servisidir.

## Bu proje ne **değildir**

- Sahaya alınmış, sertifikalı veya operasyonel olarak doğrulanmış bir sistem **değildir**.
- Klinik, acil müdahale veya operasyonel kullanıma uygunluk **iddiası taşımaz**.
- İnsan arama ekiplerinin veya yerleşik arama-kurtarma yordamlarının yerine geçmez.
- Ölçülen başarımı (aşağıda) güvenilebilecek bir seviyenin çok uzağında olan bir
  öğrenci prototipidir.

Üretilen her çıktı, bir insan operatör tarafından incelenmek üzeredir.

## Ölçülmüş taban çizgisi

Henüz model eğitimi yapılmadı. Aşağıdaki sayılar, hazır bir COCO önceden eğitilmiş
modelin (Ultralytics `yolo11n`) karolamalı ve CPU üzerinde çalıştırıldığında
ulaştığı başlangıç noktasını ölçer. Eşleştirme IoU ≥ 0,3, güven eşiği 0,30.

| Kapsam | Görüntü | Kutu | Recall | FP / görüntü |
|---|---:|---:|---:|---:|
| Tüm veri kümesi | 1579 | 3073 | 0,3160 | 0,89 |
| Baskın kaynak (ZRI) hariç | 1453 | 1776 | **0,2663** | **0,74** |

Veri kümesindeki 17 çekim kaynağı çok dengesiz dağılmıştır; tek bir kaynak (ZRI)
tüm etiketlerin %42'sini taşır, bu yüzden ZRI hariç satır daha temsili olandır.
Ölçüm tekrarlandığında sonuç tablosunun her hücresi birebir aynı çıktı.

Bu README'deki tüm sayılar depodaki ölçüm script'lerinden gelir; hiçbiri tahmin
değildir. Ham çıktılar `reports/` altındadır ve her CSV, üretildiği koşulları
(model, parametreler, kütüphane sürümleri, tarih, komut) `kosu_` önekli
sütunlarında taşır.

## Veri kümesi

[HERIDAL](http://ipsar.fesb.unist.hr/HERIDAL%20database.html) — arama-kurtarma için
havadan insan tespiti veri kümesi.

> Božić-Štulić, D., Marušić, Ž., Gotovac, S. (2019). *Deep Learning Approach in
> Aerial Imagery for Supporting Land Search and Rescue Missions.* International
> Journal of Computer Vision, 127, 1256–1278.

**CC BY 4.0** ile dağıtılan bir Roboflow Universe kopyası üzerinden erişildi. Veri
kümesi bu depoya **dahil değildir**; `data/` gitignore'dadır. Görüntü çözünürlüğü
varsayılmadı, dosyalardan doğrulandı.

## Nasıl çalıştırılır

Docker ve Docker Compose gerekir.

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # çıktıyı DJANGO_SECRET_KEY'e yaz
# .env içindeki POSTGRES_PASSWORD değerini de değiştir
```

`DJANGO_SECRET_KEY` için kodda gizli bir varsayılan yoktur; boş bırakılırsa
uygulama açılmaz.

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
curl -i http://localhost:8000/api/health/     # beklenen: 200 {"status":"ok","database":"ok"}
```

Admin paneli: <http://localhost:8000/admin/>. Ayrıntı: `backend/README_hafta1.md`.

Ölçüm script'leri Docker dışında, yerel bir veri kümesi kopyasıyla çalışır;
bkz. `README_hafta0.md`.

## Klasör yapısı

```
gozcu/
├── backend/           Django + DRF servisi (görev, kare, tespit)
├── scripts/           ölçüm ve analiz script'leri (henüz eğitim yok)
├── reports/           üretilen CSV/PNG çıktıları — gitignore'da
├── rapor/             proje raporu bölümleri
├── data/              HERIDAL veri kümesi — gitignore'da, dağıtılmaz
├── tests/             IoU ve eşleştirme testleri
└── docker-compose.yml
```

## Lisans

**AGPL-3.0.** Proje, AGPL-3.0 lisanslı Ultralytics YOLO kullanır; herkese açık bir
türev çalışma olduğu için bu depo da aynı lisansı taşır. Bkz. [LICENSE](LICENSE).
HERIDAL veri kümesi kendi CC BY 4.0 koşullarına tabidir ve burada yeniden
dağıtılmaz.
