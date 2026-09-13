# Security policy

Gözcü is an undergraduate graduation project — a research and education
prototype. It has not been penetration tested, scanned or reviewed by anyone
other than its author, and it is not meant to be exposed to the internet.

Please read that as context for everything below.

## Supported versions

Only the current `main` branch. There are no releases and no backports.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting:

**[Report a vulnerability](https://github.com/onurrkayaa/gozcu/security/advisories/new)**

That channel is enabled on this repository and the report stays private until it
is resolved. Please do not open a public issue for a security problem.

There is no separate security email address for this project.

What helps:

- what the problem is, and which file or endpoint it affects
- steps to reproduce, or a request that shows it
- what an attacker gains
- the commit you tested against

Please remove tokens, passwords and absolute paths from anything you attach.

This is a student project, not a maintained product, so expect a reply in days
rather than hours, and no guaranteed timeline for a fix.

## In scope

- The Django API in `backend/` — authentication, mission-membership
  authorisation, file upload, the frame image endpoint, the audit log
- The React interface in `frontend/`
- The Docker Compose deployment and its configuration defaults
- Secrets or credentials accidentally committed to this repository

## Out of scope

These are **known and documented**, not undiscovered. Reporting them is welcome
but they are already written down in
[docs/GUVENLIK.md](docs/GUVENLIK.md) (Turkish) with the reasoning:

- **The session token is kept in `localStorage`.** The backend has no HTTP-only
  cookie endpoint, so an XSS flaw would mean session theft. Accepted limit.
- **The refresh endpoint does not rotate tokens** and there is no blacklist, so a
  stolen refresh token stays valid for its lifetime (12 hours).
- **There is no TLS.** The stack speaks plain HTTP and binds to localhost.
  `DJANGO_HTTPS=1` enables HSTS, secure cookies and the HTTPS redirect, but only
  means something behind a reverse proxy that terminates TLS.
- **The audit log is protected at the ORM level only.** Direct database access
  bypasses it.
- **Rate limits are decisions, not measured thresholds.** They slow brute force
  down; they do not stop it.
- **No dependency audit runs as a gate.** Versions are pinned to the versions the
  measurements were taken with. `pip-audit` and `npm audit` have not been run, so
  no claim of "clean" is made here.
- Findings that require access to the host running the stack.
- The HERIDAL dataset and the trained weights — neither is in this repository.

## What is in place

Verified by tests in `backend/tests/` and by the workflows in `.github/workflows/`:

- Every endpoint requires authentication except `/api/health/`.
- Access is scoped to mission membership; a non-member gets `404`, not `403`, so
  the existence of a record does not leak.
- `/media/` is closed. Images come only from an endpoint that checks membership
  and reads the filename from the database, never from the request.
- Uploads are validated as real images by content, not by extension.
- The audit log refuses updates and deletes, drops sensitive keys and truncates
  values.
- `DEBUG` is off by default; the secret key is required with no fallback; CORS is
  an explicit allowlist with no wildcard.
- `nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: same-origin` are set in
  every environment.
- Login and refresh have their own narrow rate-limit bucket.
- Celery accepts `json` only, never pickle.
- PostgreSQL and Redis are not published to the host; the backend container runs
  as a non-root user.
- `scripts/depo_denetimi.py` scans tracked files and history for secrets, weights
  and large files, and runs as a CI gate. GitHub secret scanning and push
  protection are enabled on the repository.

None of this means the system is secure. It means these specific things were
checked.
