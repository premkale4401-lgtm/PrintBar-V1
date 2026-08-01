# PrintBar Backend — Production Dockerfile
# Multi-stage build for minimal production image.
# Stage 1: Builder — installs Python dependencies.
# Stage 2: Runtime — slim image, no build tools.

# ─── Stage 1: Dependency Builder ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install minimal system dependencies required for compilation.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first.
RUN pip install --upgrade pip==24.3.1

# Copy requirements and install into a target directory.
COPY requirements/base.txt requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Stage 2: Production Runtime ──────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create a non-root user.
RUN groupadd --system printbar && useradd --system --gid printbar printbar

# Install only runtime system libraries (no build tools).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the builder stage.
COPY --from=builder /install /usr/local

# Copy the application source.
COPY --chown=printbar:printbar . /app

# Switch to non-root user.
USER printbar

# Expose the application port.
EXPOSE 8000

# Health check using the /health endpoint.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run Uvicorn with production settings.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--access-log"]
