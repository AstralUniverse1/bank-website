FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    GUNICORN_WORKERS=2 \
    GUNICORN_THREADS=4 \
    GUNICORN_TIMEOUT=60 \
    HOME=/tmp

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt

RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home-dir /app appuser \
    && pip install --no-cache-dir -r backend/requirements.txt

COPY --chown=appuser:appuser backend/ backend/
COPY --chown=appuser:appuser frontend/ frontend/

RUN rm -f /app/backend/*.db \
    && chown -R appuser:appuser /app

EXPOSE 5000

USER 10001:10001

CMD ["sh", "-c", "gunicorn --chdir backend --bind 0.0.0.0:${PORT} --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --timeout ${GUNICORN_TIMEOUT} app:app"]


# build: docker build -t bank-app .
# run: docker run -p 5000:5000 bank-app
# run persistent: docker compose -f docker-compose.sqlite.yml up -d
# remove volume later: docker compose -f docker-compose.sqlite.yml down -v
