# Bank Website

Banking web app used to showcase a production-style Flask container, CI image validation, Docker image publishing, and GitOps deployment.

## Application

- Flask backend served by Gunicorn on port 5000 in the Docker image.
- HTML/CSS/JS frontend served by Flask.
- SQLite is used by default for local/demo runs.
- MySQL is used when `MYSQL_HOST` is defined.
- The SQLite database file is generated on demand and is not tracked in Git.
- Health endpoint: `GET /healthz`.
- Readiness endpoint with database check: `GET /readyz`.

Local development can still run the Flask entrypoint directly:

```bash
python3 backend/app.py
```

The container runtime is the production path.

## CI

GitHub Actions builds and validates the Docker image on `main` pushes and manual runs:

- Lints the Dockerfile with Hadolint.
- Builds the image.
- Scans the image with Trivy.
- Runs a container smoke test for `/healthz`, `/readyz`, and the login page.
- Pushes `astraluniverse/bank-app` with `latest`, full commit SHA, and short SHA tags.

## Container Runtime

The Docker image runs as a non-root user and starts Gunicorn with configurable defaults:

- `PORT=5000`
- `GUNICORN_WORKERS=2`
- `GUNICORN_THREADS=4`
- `GUNICORN_TIMEOUT=60`

Local SQLite mode remains available in the container for quick validation, while Kubernetes deployments use MySQL through environment configuration.

## Local Docker Run

```bash
docker build -t bank-app .
docker run -p 5000:5000 bank-app
```

For a persistent local SQLite volume:

```bash
docker compose -f docker-compose.sqlite.yml up -d
docker compose -f docker-compose.sqlite.yml down -v
```

## GitOps Deployment

Kubernetes deployment is managed in the companion GitOps repo:

https://github.com/AstralUniverse1/bank-gitops

That repo owns the Helm chart, ArgoCD Application, and manual image promotion workflow.
