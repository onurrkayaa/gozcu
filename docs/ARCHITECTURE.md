# Architecture

How the pieces fit together and why they are arranged this way. The README has
the overview; this document has the reasoning and the boundaries. Day-to-day
commands live in [GELISTIRME.md](GELISTIRME.md) (Turkish), the threat model in
[GUVENLIK.md](GUVENLIK.md) (Turkish).

---

## 1. The constraint everything follows from

One 4000×3000 image becomes roughly 80 tiles of 512 px at 20% overlap, and each
tile is a separate forward pass. On CPU the median frame takes **19.9 seconds**
end to end (measured over 157 frames, `reports/gercek_onnx_celery_sure.csv`).

A scan therefore cannot happen inside an HTTP request. Almost every structural
decision below is a consequence of that single number.

## 2. Components

| Component | Responsibility |
|---|---|
| nginx | Serves the built SPA, proxies `/api` and `/admin` to the API, returns 404 for `/media/` |
| Django + DRF (gunicorn) | Authentication, authorisation, CRUD, enqueueing runs, serving frame images |
| PostgreSQL + PostGIS | All records; distance and clustering queries run in the database |
| Redis | Celery broker and result backend |
| Celery worker | Tiling, inference, NMS, writing detections |
| ONNX Runtime | The actual model, loaded once per worker process |

The API and the worker run the **same image** — same code, same dependencies,
different process. A task that imports something the API does not have is not a
failure mode that can occur.

## 3. Request and task flow

Starting a scan:

1. `POST /api/missions/{id}/runs/` — membership with write access is checked, the
   mission is verified to have frames, an `InferenceRun` row is created with
   status `pending`.
2. The Celery task is queued **on transaction commit**, not inline. Queueing
   before the commit lets a worker pick up a `run_id` that is not yet visible to
   it and fail with `DoesNotExist`.
3. `202 Accepted` is returned with the run id.
4. `run_inference` marks the run `running`, marks the frames `queued`, and fans
   out one `process_frame` task per frame with a chord that ends in
   `finalize_run`.
5. `process_frame` reads the image **once**, computes the tile grid, runs the
   detector per tile, maps tile coordinates back to image coordinates, applies
   NMS across tile boundaries, then deletes that frame's previous detections and
   writes the new ones.
6. The interface polls `GET /api/runs/{id}/` until the run reaches a terminal
   state, then stops polling.

### Why delete-then-write

`CELERY_TASK_ACKS_LATE` is on: the message is acknowledged only after the task
finishes, so a worker that dies mid-frame does not lose the work — the message is
redelivered. The price is that a task can run twice. Delete-then-write inside one
transaction is what makes that price payable. **The two settings are one
decision**; changing either alone produces duplicated detections or lost frames.

This was tested, not assumed: a worker container was killed with `SIGKILL` during
a scan. The killed frame was redelivered and completed, 4/4 frames reached a
terminal state, with zero lost, stuck or duplicated records
(`reports/onnx_sigkill_dayaniklilik.csv`).

### Timeouts

Soft 600 s, hard 660 s, Redis visibility timeout 900 s. The ordering
soft < hard < visibility matters: a task that is still running must never be
considered dead and handed to a second worker. The slowest measured frame was
37.4 s, so these values carry a wide margin. **The margin is a decision, not a
measurement**, and it is labelled as such in the CSV.

## 4. Data model

```
Mission ──┬── Frame ──── Detection ──── Review
          │                   ▲
          ├── InferenceRun ───┘
          ├── MissionMember
          ├── Finding
          └── AuditLog

ModelVersion ──── InferenceRun   (PROTECT: a version used by a run is never deleted)
```

Three boundaries are deliberate:

**Review is not a column on Detection.** Model output and human judgement live in
separate tables. If they shared a field, "what the model found" and "what the
operator thought" would mix irreversibly and past measurements could not be
reproduced. Uniqueness is on (detection, reviewer), so two operators disagreeing
about the same detection is preserved rather than overwritten.

**Finding carries its location provenance.** `location_source` is one of `exif`,
`manual`, `demo` or `none`, and it travels all the way to the interface. A demo
coordinate can never quietly become a real one.

**A missing location is `NULL`.** Never 0,0. Zero-zero is a real place in the
Gulf of Guinea, and a search team sent there because of a default value is the
exact failure this system must not produce.

## 5. Detector selection

`get_detector()` branches on `ModelVersion.framework`:

- `onnx` → the real Model-512 session, loaded from `ONNX_MODEL_PATH`
- `fake` → `FakeDetector`, a deterministic test detector seeded from the frame's
  SHA-256 and the tile index

If the ONNX file is missing or unloadable, the error **propagates** and the frame
goes to `failed`. There is no silent fallback to the fake detector: a broken
model that looks like it is working is worse than one that stops.

The ONNX session is shared per worker process rather than created per tile or per
frame. Reading the model from disk on every tile was the original behaviour and
fixing it was a measured, single-variable change (chapter 5 of the report).

## 6. Confidence threshold

Detections are stored with a fixed floor of 0.05 (`DETECTION_STORE_FLOOR`). The
run's own `conf_threshold` is **not** baked into what gets written.

A full scan is expensive. Storing at a low floor means any threshold can be asked
of a single run afterwards, which is also why the slider in the review screen
filters the drawing only — it never re-runs the model and never changes stored
rows. That slider is not an evaluation metric, and the interface says so.

## 7. Authorisation boundary

Access is scoped to `MissionMember`, not to `created_by`. Every view resolves its
mission through `core/yetki.py`, which:

- returns **404** (not 403) to a non-member, so the existence of a mission does
  not leak through the status code,
- returns 403 to a member without write access,
- resolves nested resources (`runs/{id}/detections`) through their own mission
  rather than trusting an id from the request.

Images are the part that is easiest to get wrong, so they have their own rule:
`/media/` is not published by Django and nginx answers it with 404. The only path
to an image is `/api/frames/{id}/image/`, which reads the `Authorization` header,
checks membership and takes the filename **from the database**. There is no
request-supplied path anywhere in that endpoint, which is what makes traversal
impossible rather than merely filtered.

## 8. Audit log

`AuditLog` is append-only: `save()` refuses a second write and `delete()` always
raises. Entries are written inside the **same transaction** as the operation they
describe, so a rolled-back operation leaves no record of having happened.

The `changes` field never receives a raw object — only a summary of fields that
actually changed, with sensitive keys dropped and values truncated.

This is protection at the ORM level. Someone with direct database access can
still alter history; the goal is to stop application code or an API endpoint from
doing it by accident or on purpose.

## 9. Clustering

Findings with coordinates are grouped by connected components (Union-Find) using
a 50 m threshold, computed by PostGIS. Real and demo provenance are clustered
**separately** so a synthetic point can never join a real one.

Two honest limits: the 50 m threshold is a decision, not a measured value — there
is no real flight data to calibrate it against — and a cluster centre is the
arithmetic mean of its members, not a measured location. The interface says both.

Findings without coordinates are not clustered at all. Collecting them into one
"no location" group would suggest a geographic relationship that does not exist.

## 10. Deployment shape

```
docker-compose.yml                    production-like (default)
docker-compose.yml + .dev.yml         development
```

Production-like: gunicorn instead of `runserver`, the built SPA served by nginx
instead of the Vite dev server, PostgreSQL and Redis with no published ports, one
exposed address (`127.0.0.1:8080`), the backend container running as uid 10001,
health checks on every service.

The model file is mounted read-only from `agirliklar/` and is not copied into the
image — repository size and licensing stay unaffected by it.

Uploaded frames live in a **named volume** in the production-like stack. A host
bind mount fails on Linux because the container is not root and does not own the
host directory; the development override binds the host directory back so the
measurement scripts can read the timing log from outside the container.

TLS is terminated nowhere in this stack. `DJANGO_HTTPS=1` turns on HSTS, secure
cookies and the HTTPS redirect, and with that flag `manage.py check --deploy`
reports zero issues — but those settings only mean something behind a reverse
proxy that actually terminates TLS.

## 11. What this architecture does not do

- No scan cancellation or restart endpoint.
- No automatic re-clustering when a finding is added; it is triggered explicitly.
- No pagination beyond the first page in the interface (20 rows, with the total
  shown separately).
- No HTTP-only cookie session; the token is in browser storage.
- No horizontal scaling story, no load testing, no GPU inference path.
