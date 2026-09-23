# Multi-stage production container for Air Resilience Network API
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./

# Install dependencies into virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir .

# Final minimal runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

# Create non-root user for security
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/sh appuser

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source code and data fixtures
COPY apps/ apps/
COPY schemas/ schemas/
COPY services/ services/
COPY data/ data/
COPY pyproject.toml ./

# Ensure uploads directory is owned by appuser
RUN mkdir -p data/uploads && chown -R appuser:appgroup /app

USER appuser

# Cloud Run injects PORT environment variable (default 8000)
ENV PORT=8000
ENV ENVIRONMENT=production
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:' + str(__import__('os').getenv('PORT', 8000)) + '/healthz')" || exit 1

# Production server entrypoint
CMD exec uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT} --workers 2 --access-log
