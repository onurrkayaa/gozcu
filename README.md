# Gozcu — Aerial Search & Rescue Human Detection

> Graduation project. Research/education prototype, not a deployed system.

## Problem

Aerial search-and-rescue imagery is 4000x3000 pixels, while the people being
searched for occupy a median of **60x59 pixels** — about **0.03%** of the image
area. Feeding such an image directly to a detector downscales it to the model's
640-pixel input, shrinking a person to roughly **9 pixels**. At that size the
target is effectively destroyed before the model ever sees it.

## Approach

Tiled inference: the image is cut into **512-pixel tiles with 20% overlap** and
each tile is scanned separately, so targets keep their original scale. Tiling is
handled by SAHI. **No model has been trained yet** — this step measures what an
off-the-shelf COCO-pretrained detector (yolo11n) achieves, to establish a baseline.

## Baseline result

Measured on all **1579 images / 3073 annotated boxes**, CPU only:

| Scope | Recall @ conf 0.30 | False positives per image |
|---|---|---|
| Full dataset | 0.316 | 0.89 |
| Excluding the dominant source | **0.266** | 0.74 |

The dataset contains 17 distinct capture sources with very uneven distribution; a
single source (an urban park) holds 42% of all annotations and dominates the test
split. Excluding it gives the more representative figure of **0.266** — roughly one
in four people found, at under one false alarm per image.

Tiling is not optional here: without it, the same detector finds 43 of 252 people at
the lowest threshold, and **zero** at conf 0.30.

## Key finding

Recall correlates with target size in pixels: **r = +0.90** across sources with at
least 100 annotated boxes (Pearson). The correlation strengthens as small-sample
sources are excluded, indicating a real relationship rather than noise.

A second group of sources underperforms what their target size predicts. A contrast
hypothesis was tested and rejected (r = -0.07). The cause remains unidentified.

## Stack (planned)

Django 5 + Django REST Framework, PostgreSQL/PostGIS, Celery + Redis, React,
PyTorch with ONNX export.

## Status

**Step 1 of 9 complete** — data validation, tiling comparison, baseline measurement,
target size analysis.

## Data

HERIDAL aerial human detection dataset (Bozic-Stulic, Marusic & Gotovac, 2019),
accessed through a Roboflow Universe mirror, licensed **CC BY 4.0**. Image
resolution was verified as 4000x3000 rather than assumed.

Model weights: Ultralytics yolo11n, AGPL-3.0.

---

# Turkce

Havadan cekilmis arama-kurtarma goruntulerinde kayip insan tespiti uzerine bitirme
projesi. Bu asamada model egitimi yapilmadi; hazir bir COCO modelinin karolamali
calistirildiginda ne kadarini buldugu olculdu.

- **Kurulum ve calistirma:** `README_hafta0.md`
- **Adim 1 raporu:** `rapor/bolum_01.md`
- **Olcum ciktilari:** `reports/` (dosya listesi icin `README_hafta0.md` bolum 6)
- **Rapor uretimi:** `.venv/bin/python scripts/06_rapor_uret.py` → `rapor/rapor.pdf`
