FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY entrypoint.sh ./entrypoint.sh
RUN pip install --no-cache-dir . && chmod +x ./entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
