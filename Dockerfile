FROM python:3.11-slim

WORKDIR /app

COPY backend/ backend/
COPY frontend/ frontend/

RUN python -m pip install --upgrade --no-cache-dir pip \
    && pip install --no-cache-dir -r backend/requirements.txt

EXPOSE 5000

CMD ["python", "backend/app.py"]


# build: docker build -t bank-app .
# run: docker run -p 5000:5000 bank-app
# run persistent: docker compose -f docker-compose.sqlite.yml up -d
# remove volume later: docker compose -f docker-compose.sqlite.yml down -v
