# Railway Dockerfile for Python backend
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Expose port (Railway will set $PORT)
EXPOSE 8000

# Start command
CMD cd backend && uvicorn main_trial_class:app --host 0.0.0.0 --port ${PORT:-8000}

