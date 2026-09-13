# Third-party notices

Gözcü is licensed under [AGPL-3.0](LICENSE). This file records the licences of
the components it depends on and of the data it was measured against.

This is a record of the metadata that was reviewed, **not a legal opinion**. No
direct conflict was found among the licences listed here; that is not the same
statement as full legal compliance.

## Why AGPL-3.0

Ultralytics YOLO — used to train Model-512 and referenced by the tiling pipeline
— is distributed under AGPL-3.0. Rather than pick a permissive licence that would
sit awkwardly next to it, this repository uses AGPL-3.0 as well.

## Dataset

**HERIDAL** — aerial human detection dataset for search and rescue.

> Božić-Štulić, D., Marušić, Ž., Gotovac, S. (2019). *Deep Learning Approach in
> Aerial Imagery for Supporting Land Search and Rescue Missions.* International
> Journal of Computer Vision, 127, 1256–1278.
> DOI: [10.1007/s11263-019-01177-1](https://doi.org/10.1007/s11263-019-01177-1)

The copy used here came from a Roboflow mirror, published there under
**CC BY 4.0**. The citation above is reproduced unchanged from its source.

**The dataset licence is not the code licence.** CC BY 4.0 governs the images and
annotations; AGPL-3.0 governs this repository's code. The dataset is not included
here and has to be obtained separately.

## Model

**Ultralytics YOLO11** (`yolo11n`) — AGPL-3.0. Model-512 was trained from the
`yolo11n` architecture on tiled HERIDAL data. The trained weights are not in this
repository.

## Runtime dependencies

### Backend

| Component | Licence |
|---|---|
| Django | BSD-3-Clause |
| Django REST Framework | BSD-3-Clause |
| djangorestframework-simplejwt | MIT |
| django-cors-headers | MIT |
| psycopg | LGPL-3.0-only |
| Celery | BSD-3-Clause |
| redis-py | MIT |
| Pillow | MIT-CMU |
| ONNX Runtime | MIT |
| gunicorn | MIT |
| whitenoise | MIT |
| python-dotenv | BSD-3-Clause |

### Analysis and training

| Component | Licence |
|---|---|
| Ultralytics | AGPL-3.0 |
| SAHI | MIT |
| ONNX | Apache-2.0 |
| NumPy | BSD-3-Clause |
| pandas | BSD-3-Clause |
| matplotlib | PSF-based (matplotlib licence) |
| ReportLab | BSD-3-Clause |
| pytest | MIT |

### Frontend

| Component | Licence |
|---|---|
| React, React DOM | MIT |
| React Router | MIT |
| TanStack Query | MIT |
| Leaflet | BSD-2-Clause |
| react-leaflet | Hippocratic-2.1 |
| Vite | MIT |
| TypeScript | Apache-2.0 |
| Vitest | MIT |
| ESLint | MIT |
| Testing Library | MIT |

### Infrastructure images

| Image | Licence |
|---|---|
| `python:3.13-slim-bookworm` | PSF (Python) + Debian package licences |
| `node:24-bookworm-slim` | MIT (Node.js) + Debian package licences |
| `nginx:1.29-alpine` | BSD-2-Clause |
| `redis:8.10.1-alpine` | RSALv2 / SSPLv1 (Redis 8) |
| `imresamu/postgis:16-3.5` | PostgreSQL licence + GPL-2.0-or-later (PostGIS) |

## Map data

Map tiles are served by **OpenStreetMap**. Map data is © OpenStreetMap
contributors, available under the **Open Database License (ODbL)**. The
attribution is displayed in the interface, as the tile usage policy requires.

## Screenshots

The screenshots in `docs/images/` and `rapor/gorseller/` were produced by running
this project locally. Those showing aerial imagery show HERIDAL images and are
covered by the dataset's CC BY 4.0 licence. Coordinates visible in map
screenshots are synthetic demo data.
