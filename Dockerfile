FROM python:3.12-slim

LABEL maintainer="holocronology"
LABEL description="Piratarr - Pirate speak subtitle generator for your media library"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIRATARR_CONFIG_DIR=/config \
    PIRATARR_PORT=6969

# Create app user
RUN groupadd -g 1000 piratarr && \
    useradd -u 1000 -g piratarr -m piratarr

# Install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY piratarr/ piratarr/
COPY entrypoint.py .

# Create config directory
RUN mkdir -p /config && chown piratarr:piratarr /config

# Expose port
EXPOSE ${PIRATARR_PORT}

# Volume for persistent config/database
VOLUME /config

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:${PIRATARR_PORT}/api/status', timeout=5).raise_for_status()" || exit 1

USER piratarr

ENTRYPOINT ["python", "entrypoint.py"]
