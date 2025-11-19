# Railway Dockerfile for SalesBestFriend Backend
FROM python:3.11-slim

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy backend directory
WORKDIR /app/backend
COPY backend/ /app/backend/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8000

# Start uvicorn (already in /app/backend)
CMD uvicorn main_trial_class:app --host 0.0.0.0 --port ${PORT:-8000}

