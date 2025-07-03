FROM python:3.11.2

# Install dependencies including updated sqlite3
RUN apt-get update && \
    apt-get install -y wget build-essential libsqlite3-dev sqlite3 && \
    wget https://www.sqlite.org/2023/sqlite-autoconf-3430000.tar.gz && \
    tar xzf sqlite-autoconf-3430000.tar.gz && \
    cd sqlite-autoconf-3430000 && \
    ./configure && make && make install && \
    cd .. && rm -rf sqlite-autoconf-3430000*

# Recompile Python to use the updated SQLite (optional for system Python but good practice)
ENV LD_LIBRARY_PATH=/usr/local/lib
RUN ln -sf /usr/local/lib/libsqlite3.so.0 /usr/lib/libsqlite3.so.0

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose app port
EXPOSE 8033

# Default command
CMD ["python3", "main_uagents.py"]
