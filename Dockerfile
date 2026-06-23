FROM python:3.11-slim

ARG EXAMPLE=fetch-hackathon-quickstarter

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ${EXAMPLE}/ ./

RUN pip install --no-cache-dir --upgrade pip && \
    if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        echo "No requirements.txt found for ${EXAMPLE}; skipping dependency install."; \
    fi

RUN if [ -f .env.example ] && [ ! -f .env ]; then cp .env.example .env; fi

ENTRYPOINT ["python"]
CMD ["agent.py"]
