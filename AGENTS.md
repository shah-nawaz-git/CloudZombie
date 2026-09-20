# Repository agent guide

## Design authority

`docs/architecture.md` is the design authority. Read it before changing domain vocabulary, persistence, provider behavior, reconciliation, pricing, remediation, API contracts, demo evaluation, or configuration. If code and architecture disagree, fix the disagreement explicitly rather than allowing silent drift.

## Backend

From `backend/`:

```bash
./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m ruff format --check .
./.venv/Scripts/python.exe -m mypy app
./.venv/Scripts/python.exe -m pytest -q
```

Use `./.venv/bin/python` on Linux/macOS. Install with:

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

Run locally:

```bash
CLOUDZOMBIE_MODE=demo DATABASE_URL=sqlite:///./cloudzombie.db ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

## Frontend

From `frontend/`:

```bash
npm install
npm run lint
npm run format:check
npx tsc --noEmit
npm run test
npm run build
```

Run against the backend:

```bash
BACKEND_URL=http://localhost:8000 npm run dev
```

End to end:

```bash
E2E_BASE_URL=http://localhost:3000 npx playwright test
```

## Demo

Docker flow:

```bash
docker compose up --build
```

Bash helper flow:

```bash
scripts/dev-backend.sh
scripts/dev-frontend.sh
```

Reset demo data only with explicit confirmation:

```bash
cd backend
./.venv/Scripts/python.exe -m app.cli demo reset --yes
```

## Conventions

- Only `backend/app/providers/aws/` may import boto3 or botocore clients.
- CloudZombie's runtime never calls mutating AWS APIs.
- Do not modify Bash text in `backend/app/remediation/scripts/templates.py` without demonstrating the shellcheck reason and re-running golden, shellcheck, injection, behavioural, and destructive-call tests.
- Treat resource age and condition-observation age as separate facts.
- Use “snapshot with deleted source volume,” “known dependencies,” and “estimated monthly list-price exposure.”
- Preserve timezone-aware UTC datetimes.
- Preserve LF endings; `.gitattributes` enforces LF for shell and Python files.
- Do not commit secrets, database files, credentials, generated coverage, Playwright artifacts, virtual environments, or node modules.
- Prefer focused changes and narrow verification before the final consolidated pass.

## Full verification

The aggregate Bash script runs backend and frontend checks:

```bash
scripts/check-all.sh
```

Also validate shell scripts:

```bash
backend/.venv/Scripts/shellcheck.exe -s bash -S style backend/tests/golden/*.sh backend/entrypoint.sh scripts/*.sh
```

Before reporting, run `git diff --check` and `git status --short`. Docker and live AWS verification must be reported honestly; unit tests using moto/Stubber are not live-AWS verification.
