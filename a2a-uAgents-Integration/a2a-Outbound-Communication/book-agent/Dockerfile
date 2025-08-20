FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y gcc \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
EXPOSE 8033
CMD ["python", "main.py"]