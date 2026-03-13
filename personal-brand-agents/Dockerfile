FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY data_management_agent/ ./data_management_agent/
COPY utils/ ./utils/
COPY shared_clients/ ./shared_clients/
COPY database/ ./database/
COPY wrapped_uagents/ ./wrapped_uagents/
COPY brand_agent/ ./brand_agent/
COPY chroma/ ./chroma/
COPY entrypoint.sh /app/entrypoint.sh


# Expose the port the agent runs on
EXPOSE 8080

# Set environment variable for Python path
ENV PYTHONPATH=/app

# Run the wrapped data management agent services
ENTRYPOINT ["/app/entrypoint.sh"]