FROM python:3.11-slim

ARG EXAMPLE=fetch-hackathon-quickstarter

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copied before the install so that examples shipping no requirements.txt still
# build: COPYing a file that does not exist is a hard build failure, whereas a
# shell test after the fact can skip cleanly.
COPY ${EXAMPLE}/ ./

RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir --upgrade pip && \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        echo "No requirements.txt for ${EXAMPLE}; skipping dependency install."; \
    fi

RUN if [ -f .env.example ] && [ ! -f .env ]; then cp .env.example .env; fi

ENTRYPOINT ["python"]
CMD ["agent.py"]
