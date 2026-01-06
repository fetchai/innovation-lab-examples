FROM python:3.10-slim

WORKDIR /app

# Install Node.js (required for Firecrawl MCP server via npx)
# Node.js >= 22.0.0 is required according to agent.py
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent files
COPY agent.py .
COPY __init__.py .

# Expose port for the SEO audit agent
EXPOSE 8007

# Default command (can be overridden in docker-compose)
CMD ["python", "agent.py"]
