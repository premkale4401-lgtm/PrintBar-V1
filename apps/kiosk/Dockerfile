FROM python:3.12-slim-bookworm

# Install system CUPS client libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcups2-dev \
    cups-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -r -s /bin/bash printbar
WORKDIR /opt/printbar-kiosk

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY config/ ./config/

# Create directories
RUN mkdir -p /tmp/printbar /var/log/printbar && \
    chown -R printbar:printbar /opt/printbar-kiosk /tmp/printbar /var/log/printbar

USER printbar

CMD ["python", "-m", "app"]
