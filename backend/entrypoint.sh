#!/bin/sh
set -eu

attempt=1
while ! python -c 'from sqlalchemy import create_engine, text; from app.core.config import get_settings; engine = create_engine(get_settings().database_url); connection = engine.connect(); connection.execute(text("SELECT 1")); connection.close()' >/dev/null 2>&1; do
  if [ "$attempt" -ge 30 ]; then
    echo "Database did not become ready after 30 attempts." >&2
    exit 1
  fi
  echo "Waiting for database (attempt $attempt/30)..."
  attempt=$((attempt + 1))
  sleep 2
done

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
