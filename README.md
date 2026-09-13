# Gözcü

**Havadan çekilmiş arama-kurtarma görüntülerinde insan adayı tespiti için
operatör destek prototipi.**

Lisans bitirme projesi — eğitim ve araştırma amaçlıdır.

> 🇬🇧 [English summary below](#english-summary)

| | |
|---|---|
| **Beş dakikada görmek için** | [`./demo.sh`](DEMO.md) |
| **Tam rapor (Türkçe, 8 bölüm)** | [rapor/GOZCU_RAPOR_TR.md](rapor/GOZCU_RAPOR_TR.md) |
| **Geliştirme rehberi** | [docs/GELISTIRME.md](docs/GELISTIRME.md) |
| **Güvenlik modeli ve sınırları** | [docs/GUVENLIK.md](docs/GUVENLIK.md) |
| **Ölçüm çıktıları** | [reports/](reports/README.md) |

---

## Gözcü nedir

Arama-kurtarma uçuşlarından gelen fotoğraflar büyüktür (4000×3000 piksel),
aranan insan ise küçüktür: etiketli kutuların medyanı **60×59 piksel**, yani
görüntü alanının yaklaşık **%0,03'ü**. Böyle bir görüntü doğrudan bir dedektöre
verilirse model onu 640 piksele küçültür ve 60 piksellik bir insan ~9 piksele
iner; bu boyutta tespit pratikte imkânsızdır.

Gözcü her görüntüyü **512 piksellik karolara** böler (%20 örtüşmeyle, SAHI ile),
her karoyu ayrı tarar ve sonuçları birleştirir. Böylece hedefler kendi
ölçeklerini korur. Çıkan adaylar bir **insan operatörün** incelemesi için
arayüze düşer.

Sistem üç parçadır: tarama işini kuyruğa alan bir Django + PostGIS servisi, işi
yürüten bir Celery işçisi ve operatörün karar verdiği bir React arayüzü.

## Gözcü ne **değildir**

- Dağıtılmış, sertifikalı veya sahada doğrulanmış bir sistem **değildir**.
- Acil durum müdahalesine uygunluk iddiası **taşımaz**.
- Arama ekiplerinin veya yerleşik arama-kurtarma yordamlarının yerine
  **geçmez**.
- Ölçülmüş doğruluğu, güvenilmesi gereken bir seviyenin **çok altındadır**.

Her çıktı bir insan operatörün incelemesi içindir. Bu ifade uygulamanın her
sayfasında da yazılıdır ve kapatılamaz.

## Ölçülmüş ana sonuç

Kendi verimizle eğitilen **Model-512**, hazır COCO ağırlığıyla kurulan taban
çizgisiyle **aynı test kümesinde, aynı protokolde ve aynı yanlış pozitif
bütçesinde** karşılaştırıldı.

Test bölümü: 157 görüntü, 970 hedef. Protokol: karo 512, örtüşme 0,20, IoU 0,30, CPU.

| Koşu | conf | Recall | FP/görüntü |
|---|---|---|---|
| Taban-512 (COCO, eğitim yok) | 0,30 | 0,3804 | 1,81 |
| **Model-512 (kendi verimizle eğitildi)** | **0,53** | **0,6825** | **1,75** |

Karşılaştırma noktası **eşik değil bütçedir**: aynı eşikte karşılaştırmak iki
modeli aynı yerde karşılaştırmayı garanti etmez, çünkü operatöre yansıyan şey
eşiğin sayısı değil görüntü başına kaç yanlış kutuya bakmak zorunda kaldığıdır.
Tabanın 1,81'lik bütçesine sığan ilk nokta conf 0,53'tür.

Orada recall **0,3804'ten 0,6825'e** çıkıyor — 1,79 kat, 293 ek hedef — ve bunu
yaparken yanlış pozitif yükü **artmıyor** (1,75 karşı 1,81).

Kaynak: `reports/test_taban_cizgisi.csv`, `reports/test_model512.csv`,
`reports/esik_taramasi.csv` (`scripts/01_taban_cizgisi.py`).

> Bu sayı, Kaggle eğitim çıktısındaki mAP değeriyle **karşılaştırılamaz**: farklı
> küme, farklı protokol, farklı metrik.

## En önemli kısıtlar

Bunlar sonucu okurken bilinmesi **zorunlu** olan sınırlardır.

- **Kaynak aşinalığı.** Test hedeflerinin 939/970'i tek bir kaynaktan (ZRI)
  geliyor ve ZRI eğitim kümesinde de var. Sonuçlar bu kaynağa aşina bir model
  için geçerlidir. *Veri sızıntısı değildir*: 1579 görüntünün SHA-256 özeti
  hesaplandı, bölümler arasında ortak dosya **sıfır**.
- **Gerçek GPS yok.** Veri kümesindeki 1579 görüntünün hiçbirinde EXIF GPS
  bulunmuyor. Arayüz koordinat **üretmez**; haritadaki her koordinat elle
  girilmiş veya açıkça "demo" etiketli sentetik değerdir.
- **Model-320 yok.** 2×2 deney matrisinin dördüncü hücresi boştur; karo boyutu
  ile model ölçeği arasındaki etkileşim ölçülmedi.
- **Yerel dağıtım.** Sistem yerel makinede, düz HTTP üzerinde çalışır. Gerçek
  bir internet dağıtımı, TLS veya yük testi **yoktur**.
- **Oturum belirteci tarayıcı deposunda.** Bir XSS açığı oturumun çalınması
  demektir; kabul edilmiş prototip sınırıdır ([docs/GUVENLIK.md](docs/GUVENLIK.md)).
- **ONNX ağırlığı depoda yok.** 10,5 MB ikili dosya; beklenen SHA-256
  [docs/GELISTIRME.md](docs/GELISTIRME.md) bölüm 8'de yazılıdır.

Kısıtların tamamı [rapor/PROJE_DURUMU.md](rapor/PROJE_DURUMU.md) bölüm 3'tedir.

## Hızlı başlangıç

Gereken tek şey **Docker Desktop**.

```bash
git clone <depo-adresi> && cd gozcu
./demo.sh
```

Komut ortam dosyasını üretir, beş servisi başlatır, şemayı uygular, demo
verisini kurar ve adresi yazar: **<http://localhost:8080>**

Ayrıntı, demo senaryosu ve hangi verinin sentetik olduğu: [DEMO.md](DEMO.md).

## Geliştirme

```bash
cp .env.example .env      # DJANGO_SECRET_KEY ve POSTGRES_PASSWORD doldurun
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
cd frontend && npm install && npm run dev
```

Kurulum, komutlar, mimari ve tasarım kararları: [docs/GELISTIRME.md](docs/GELISTIRME.md).

## Test

| Ne | Komut |
|---|---|
| Backend | `docker compose exec web pytest -q` |
| Analiz script'leri | `.venv/bin/python -m pytest scripts/tests tests -q` |
| Arayüz | `cd frontend && npm test` |
| Lint + tür denetimi | `cd frontend && npm run lint && npm run typecheck` |
| Depo denetimi | `python3 scripts/depo_denetimi.py` |

Aynı adımlar her push ve pull request'te GitHub Actions üzerinde koşar
(`.github/workflows/`). Veri kümesi ve model ağırlıkları CI'ya indirilmez.

## Teknoloji

| Katman | Seçim |
|---|---|
| API | Django 5.2 · Django REST Framework · SimpleJWT |
| Veritabanı | PostgreSQL 16 + PostGIS 3.5 |
| Kuyruk | Celery 5.6 + Redis 8 |
| Çıkarım | ONNX Runtime 1.30 · SAHI karolama |
| Model | Ultralytics `yolo11n`, 512 px karolarla eğitildi |
| Arayüz | React 19 · TypeScript · Vite · TanStack Query · Leaflet |
| Dağıtım | Docker Compose · gunicorn · nginx |

## Veri kümesi

[HERIDAL](http://ipsar.fesb.unist.hr/HERIDAL%20database.html) — arama-kurtarma
için havadan insan tespiti veri kümesi. Depoda **yoktur**.

> Božić-Štulić, D., Marušić, Ž., Gotovac, S. (2019). *Deep Learning Approach in
> Aerial Imagery for Supporting Land Search and Rescue Missions.* International
> Journal of Computer Vision, 127, 1256–1278.
> DOI: [10.1007/s11263-019-01177-1](https://doi.org/10.1007/s11263-019-01177-1)

Kullanılan kopya bir [Roboflow](https://universe.roboflow.com/) aynasından
alınmıştır ve orada **CC BY 4.0** ile yayımlanmıştır. Künye değiştirilmeden
aktarılmıştır.

## Lisans

[AGPL-3.0](LICENSE).

Ultralytics YOLO da AGPL-3.0 ile dağıtılmaktadır; bu depo aynı lisansı
kullanarak uyumlu kalır. Leaflet BSD-2-Clause, harita karoları
OpenStreetMap katkıcılarına aittir (ODbL) ve arayüzde atıfları görünür.

## Depo düzeni

```
backend/    Django + DRF + Celery          docs/     rehber ve güvenlik modeli
frontend/   React + TypeScript + Vite      rapor/    Türkçe rapor (8 bölüm)
scripts/    ölçüm ve analiz script'leri    reports/  ölçüm çıktıları (CSV)
```

Model ağırlıkları (`agirliklar/`) ve veri kümesi (`data/`) Git'te yoktur.

## Güvenlik bildirimi

Bir güvenlik sorunu bulursanız depoda bir konu (issue) açın. Tehdit modeli,
uygulanan kontroller ve **açıkça kabul edilmiş riskler**:
[docs/GUVENLIK.md](docs/GUVENLIK.md).

---

# English summary

**Gözcü** is an operator-support prototype for detecting people in aerial
search-and-rescue imagery. Undergraduate graduation project — research and
education only.

Aerial SAR photographs are large (4000×3000 px) while the people in them are
small — a median annotated box of 60×59 px, about 0.03% of the image area.
Passing such an image straight to a detector downscales it to the model's 640 px
input, shrinking the median target below 10 px across. Gözcü scans each image as
512 px tiles with 20% overlap (via SAHI) so targets keep their original scale,
and presents candidates to a human operator for review.

**This is not** a deployed, certified or operationally validated system, and it
does not replace human search teams or any established SAR procedure.

### Measured result

A model trained on our own tiled data (**Model-512**) compared against an
off-the-shelf COCO baseline on the **same test split, same protocol and the same
false-positive budget**. Test split: 157 images, 970 targets; tile 512, overlap
0.20, IoU 0.30, CPU.

| Run | conf | Recall | FP / image |
|---|---|---|---|
| Baseline-512 (COCO, no training) | 0.30 | 0.3804 | 1.81 |
| **Model-512 (trained on our data)** | **0.53** | **0.6825** | **1.75** |

The comparison point is the **budget, not the threshold**: what reaches the
operator is not the confidence number but how many false boxes they must review
per image. Within the baseline's budget, recall rises from 0.3804 to 0.6825
(1.79×, 293 additional targets) without increasing the false-positive load.

This figure is **not comparable** to the mAP reported by the training run — a
different split, protocol and metric.

### Key limitations

- **Source familiarity:** 939 of 970 test targets come from one capture source
  (ZRI) that is also present in training. Not data leakage — SHA-256 digests of
  all 1579 images show zero overlap between splits — but the result holds for a
  model familiar with that source.
- **No real GPS:** none of the 1579 images carries EXIF GPS. The interface never
  invents coordinates; every map coordinate is either manually entered or
  explicitly labelled synthetic demo data.
- **Local deployment only:** plain HTTP on a local machine. No TLS, no internet
  deployment, no load testing.
- **Session token in browser storage:** an XSS flaw means session theft. An
  accepted prototype limit, documented in `docs/GUVENLIK.md`.

### Running it

Docker Desktop is the only prerequisite:

```bash
./demo.sh          # builds, starts five services, seeds demo data
```

Then open <http://localhost:8080>. See [DEMO.md](DEMO.md) for the walkthrough and
for exactly which data is synthetic.

The full report is in Turkish: [rapor/GOZCU_RAPOR_TR.md](rapor/GOZCU_RAPOR_TR.md).

Licensed under [AGPL-3.0](LICENSE). Dataset: HERIDAL (citation above), used from
a Roboflow mirror published under CC BY 4.0.
