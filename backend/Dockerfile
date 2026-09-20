FROM python:3.12-slim

WORKDIR /app
COPY backend/pyproject.toml backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY backend/entrypoint.sh ./entrypoint.sh
COPY fixtures ./fixtures
ENV CLOUDZOMBIE_DEMO_FIXTURE=/app/fixtures/demo/dataset.json
RUN pip install --no-cache-dir . && chmod +x ./entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
