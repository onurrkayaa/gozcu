# Contributing

This is a graduation project, so it is small and opinionated. Issues, questions
and patches are welcome; please read this first so a pull request does not run
into a rule it could not have known about.

## Getting it running

```bash
cp .env.example .env    # fill in DJANGO_SECRET_KEY and POSTGRES_PASSWORD
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
cd frontend && npm install && npm run dev
```

Full setup, commands and design notes: [docs/GELISTIRME.md](docs/GELISTIRME.md)
(Turkish).

Neither the dataset nor the model weights are needed for development or for the
tests. The demo works without them too — it falls back to generated images and a
deterministic test detector.

## Before opening a pull request

```bash
docker compose exec web pytest -q
.venv/bin/python -m pytest scripts/tests tests -q
cd frontend && npm test && npm run lint && npm run typecheck && npm run build
python3 scripts/depo_denetimi.py
```

The same steps run in CI, so it is faster to find out locally.

## Rules that are not obvious

**Do not edit the CSV files in `reports/`.** They are measurement evidence, not
generated artefacts — several took hours of CPU to produce and every number in
the report is read from them. If a measurement is wrong, add a new run with a new
file and explain the difference; do not overwrite history. Some files record
limited or failed measurements and are kept on purpose.

**A number and a CSV cannot disagree.** If the text says one thing and the CSV
says another, the CSV wins and the text gets corrected.

**New model comparisons use the same split and protocol.** Comparing at the same
confidence threshold is not enough — the comparison point is the false-positive
budget. A result produced on a different split, tile size or IoU threshold is a
different measurement and has to be labelled as one.

**Do not claim what was not measured.** The report uses explicit evidence labels
(finding / hypothesis / refuted / interesting but unproven). Keep them.

**Never commit** `.env`, model weights (`.pt`, `.onnx`), dataset files,
`node_modules`, build output, local databases or absolute paths from your
machine. `.gitignore` covers these and `scripts/depo_denetimi.py` checks that it
worked.

## Style

- Match the surrounding code. Backend and frontend identifiers are in Turkish;
  new code follows that rather than mixing languages.
- Comments explain *why*, not *what*. A comment that restates the line is noise;
  one that records a rejected alternative is worth keeping.
- Tests first for anything that has a failure mode. Backend uses pytest, frontend
  uses Vitest, analysis scripts use pytest.
- Commit messages: a short imperative line, then what changed and why. No
  generated-looking progress reports.

## Branches

Work on a branch off `main` and open a pull request. `main` is not force-pushed
and history is not rewritten.

## Issues

A useful bug report has the environment, the steps, what you expected and what
happened. Templates are provided when you open one.

## Security

Do not open a public issue for a security problem — see [SECURITY.md](SECURITY.md).
