FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install dependencies into a separate prefix for clean copy
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install .

# --- Runtime stage ---
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

RUN useradd --create-home appuser && \
    chown -R appuser:appuser /app
USER appuser

# Default: run ingestion pipeline. Override CMD for other pipelines.
CMD ["python", "-m", "pipelines.ingest_pipeline"]
