# Build from the repository root: docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend ./backend
COPY scripts ./scripts
COPY alembic.ini ./
COPY docs/benchmark ./docs/benchmark

RUN useradd --create-home visentra && mkdir -p /app/storage && chown -R visentra /app/storage
USER visentra

ENV STORAGE_ROOT=/app/storage
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=4s --start-period=40s CMD curl -fs http://localhost:${PORT:-8000}/health || exit 1
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
