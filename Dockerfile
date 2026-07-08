# ---------------------------------------------------------------------------
# Build Stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt requirements.prod.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt -r requirements.prod.txt


# ---------------------------------------------------------------------------
# Runtime Stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /install /usr/local


# Copy application source
COPY app/ ./app/
COPY frontend/ ./frontend/
COPY agents.yaml ./

# Google Cloud Run injects the PORT environment variable automatically.
# Default to 8080 for local Docker testing.
ENV PORT=8080

EXPOSE 8080

# Use exec form so signals (SIGTERM) are forwarded correctly for graceful shutdown.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
