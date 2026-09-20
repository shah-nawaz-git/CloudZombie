#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"
if [ ! -d .venv ]; then
  python -m venv .venv
fi
./.venv/Scripts/python.exe -m pip install -e '.[dev]' 2>/dev/null || ./.venv/bin/python -m pip install -e '.[dev]'
export CLOUDZOMBIE_MODE=demo
export DATABASE_URL=sqlite:///./cloudzombie.db
if [ -x ./.venv/Scripts/python.exe ]; then
  exec ./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
fi
exec ./.venv/bin/python -m uvicorn app.main:app --reload --port 8000
