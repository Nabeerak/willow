FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and data
COPY src/ src/
COPY data/ data/
COPY willow-dashboard/ willow-dashboard/

# Expose the default port for Cloud Run
ENV PORT=8080
EXPOSE 8080

# Run the application
CMD ["sh", "-c", "uvicorn src.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
