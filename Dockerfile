FROM python:3.11-slim

WORKDIR /app

COPY backend/ backend/
COPY frontend/ frontend/

RUN pip install --no-cache-dir -r backend/requirements.txt

EXPOSE 5000

CMD ["python", "backend/app.py"]

