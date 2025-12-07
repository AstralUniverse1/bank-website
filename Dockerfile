FROM python:3.11-slim

# Install system dependencies needed for SQLite
RUN apt-get update && apt-get install -y libsqlite3-dev && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Set working directory
WORKDIR /app

# Copy the app code
COPY backend/ backend/
COPY frontend/ frontend/

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Expose Flask port
EXPOSE 5000

# Start the app
CMD ["python", "backend/app.py"]
