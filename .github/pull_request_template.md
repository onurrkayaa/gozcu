## What changed

## Why

## How it was tested

<!-- Which of these you ran, and the result. -->

- [ ] `docker compose exec web pytest -q`
- [ ] `.venv/bin/python -m pytest scripts/tests tests -q`
- [ ] `cd frontend && npm test && npm run lint && npm run typecheck && npm run build`
- [ ] `python3 scripts/depo_denetimi.py`

## Effect on measurements

<!--
Leave "none" if this does not touch the detector, tiling, thresholds or the
evaluation protocol. If it does, say which measurement changes and on which
split — same split and protocol as the existing numbers, or a new one.
-->

## Effect on security or data

<!--
Anything touching authorisation, uploads, the image endpoint, the audit log or
location provenance. Otherwise "none".
-->

## Checklist

- [ ] No `.env`, model weights, dataset files or absolute paths from my machine
- [ ] Existing CSV files in `reports/` are untouched
- [ ] Documentation updated if behaviour or a command changed
