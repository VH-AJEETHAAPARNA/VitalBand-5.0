# VitalBand Backend – Production Docker Image
# Python 3.12 slim base for minimal image size

FROM python:3.12-slim

# Install OS-level dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies first (layer cache)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source (the entire vitalband package)
COPY . .

# Expose API port
EXPOSE 5000

# Health check — polls the patients endpoint every 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/patients')"

# Use PYTHONPATH so `from backend.xxx import` works correctly
ENV PYTHONPATH=/app

CMD ["python", "app.py"]
