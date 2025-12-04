# Use official Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy backend and frontend into the container
COPY backend/ ./backend
COPY frontend/ ./frontend

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Set environment variables for Flask
ENV FLASK_APP=backend/app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Expose port
EXPOSE 5000

# Run the app
CMD ["flask", "run"]
