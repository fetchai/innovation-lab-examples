FROM python:3.13-slim

# System deps (minimal, safe)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Set workdir
WORKDIR /app

# Copy dependency files first (for caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy source code
COPY . .

# Default (overridden in compose)
CMD ["bash"]
