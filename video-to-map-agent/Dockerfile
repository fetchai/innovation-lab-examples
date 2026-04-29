FROM python:3.12-slim

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Output directory for PDFs, Excel files, and map PNGs
RUN mkdir -p /app/output

# Default entrypoint — overridden per service in docker-compose.yml
CMD ["python", "orchestrator_agent.py"]
