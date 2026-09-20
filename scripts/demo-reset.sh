#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"
if [ -x ./.venv/Scripts/python.exe ]; then
  exec ./.venv/Scripts/python.exe -m app.cli demo reset --yes
fi
exec ./.venv/bin/python -m app.cli demo reset --yes
