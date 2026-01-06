FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy security agent folder
COPY security_agent/ ./security_agent/

# Expose port for security agent
EXPOSE 8008

# Default command (can be overridden in docker-compose)
CMD ["python", "security_agent/agent.py"]
