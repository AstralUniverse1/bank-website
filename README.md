# Bank Website

Containerized demo banking app with GitHub Actions CI and DockerHub image publishing.

This repo owns the application code, Docker image, and CI workflow. Kubernetes deployment is handled in the companion GitOps repo: [`bank-gitops`](https://github.com/AstralUniverse1/bank-gitops).

## Repository Structure

| Path | Purpose |
| --- | --- |
| `.github/workflows/ci.yml` | Build, scan, test, and publish Docker image |
| `backend/` | Flask app, API routes, database handler, Python requirements |
| `frontend/` | Static HTML/CSS/JS frontend |
| `Dockerfile` | Python 3.11 image running Gunicorn as a non-root user |
| `docker-compose.sqlite.yml` | Local run with persistent SQLite storage |

## Application

| Area | Details |
| --- | --- |
| Runtime | Flask served by Gunicorn on port `5000` |
| Frontend | Static files served by Flask |
| Database | SQLite by default, generated untracked; MySQL when `MYSQL_HOST` is set or `DB_ENGINE=mysql` |
| Health checks | `/healthz` and `/readyz` |

## Demo Access

The app seeds two showcase users when it starts against a new or empty database:

| User ID | Password |
| --- | --- |
| `demo_alice` | `DemoPass123` |
| `demo_bob` | `DemoPass123` |

Seed data is created only when missing, so normal app restarts preserve balances and transactions. If the local SQLite file or external MySQL database is recreated, the demo users and sample transactions are created again automatically.

Local SQLite database files are runtime artifacts and are ignored by git. The container image also removes baked-in `*.db` files and writes SQLite data to `/data/bank_website.db` by default.

## CI Workflow

The workflow runs on pushes to `main` and manual `workflow_dispatch` runs.

It builds the Docker image, runs Hadolint, scans with Trivy, smoke-tests `/healthz`, `/readyz`, and login, and pushes `astraluniverse/bank-app` to DockerHub.

## GitOps Deployment

Deployment state lives in [`bank-gitops`](https://github.com/AstralUniverse1/bank-gitops).

The `bank-gitops` promotion workflow takes a manual `image_tag` input, updates the Helm chart image tag, and lets ArgoCD sync the change to Kubernetes.
