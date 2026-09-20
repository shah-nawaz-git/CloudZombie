#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
if [ -x ./.venv/Scripts/python.exe ]; then
  PYTHON=./.venv/Scripts/python.exe
else
  PYTHON=./.venv/bin/python
fi
"$PYTHON" -m ruff check .
"$PYTHON" -m ruff format --check .
"$PYTHON" -m mypy app
"$PYTHON" -m pytest -q
cd "$ROOT/frontend"
npm run lint
npm run format:check
npx tsc --noEmit
npm run test
npm run build
