FROM python:3.12-slim

WORKDIR /app

# ffmpeg is required by pydub for MP3 encoding
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh

RUN mkdir -p /app/output

ENTRYPOINT ["/app/docker-entrypoint.sh"]
# Default command — overridden per service in docker-compose.yml
CMD ["python", "orchestrator.py"]
