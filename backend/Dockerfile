FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app

RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY backend/pyproject.toml backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY backend/entrypoint.sh ./entrypoint.sh
COPY fixtures ./fixtures
ENV CLOUDZOMBIE_DEMO_FIXTURE=/app/fixtures/demo/dataset.json
RUN pip install --no-cache-dir . \
    && chmod +x ./entrypoint.sh \
    && chown -R app:app /app /home/app

USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=12 CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status == 200 else 1)"]
ENTRYPOINT ["./entrypoint.sh"]
