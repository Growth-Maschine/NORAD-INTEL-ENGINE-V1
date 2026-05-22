# Backend Dockerfile for Railway (or any container host).
# Builds the FastAPI app from apps/api so Railway can deploy straight from
# the repo root with no "Root Directory" setting required.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for asyncpg / httpx / lxml builds.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so this layer caches when only app code changes.
COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the app. Explicit /app/ trailing slash + per-subdir copies so we know
# exactly what lands where (avoids ambiguity in docker COPY semantics).
COPY apps/api/app /app/app
COPY apps/api/tests /app/tests

# Make sure Python can find the `app` package regardless of CWD quirks.
ENV PYTHONPATH=/app
ENV PORT=8000
EXPOSE 8000

# Healthcheck hits the FastAPI /health route.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,os,sys; \
    sys.exit(0) if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8000)}/health').status==200 else sys.exit(1)"

# Pre-import app.main so any startup error surfaces in Railway logs.
CMD ["sh", "-c", "python -c 'import app.main' && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
