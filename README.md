# Bank Website

Demo banking web app used to showcase application containerization, CI, Docker image publishing, and a small EC2 remote-state workflow.

## Application

- Flask backend on port 5000.
- HTML/CSS/JS frontend served by Flask.
- SQLite is used by default for local/demo runs.
- MySQL is used when `MYSQL_HOST` is defined.
- The SQLite database file is generated on demand and is not tracked in Git.

## CI

GitHub Actions builds and validates the Docker image on `main` pushes and manual runs:

- Lints the Dockerfile with Hadolint.
- Builds the image.
- Scans the image with Trivy.
- Runs a simple container smoke test.
- Pushes `astraluniverse/bank-app` with `latest`, full commit SHA, and short SHA tags.

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

## Optional EC2 Workflow

The Terraform workflow demonstrates remote state with an S3 backend and DynamoDB lock table. It provisions a small EC2 host and security group.

The Ansible playbook configures that EC2 host with Docker and the Docker Compose plugin.

Required GitHub configuration is documented in `.github/workflows/terraform.yml`.

## GitOps Deployment

Kubernetes deployment is managed in the companion GitOps repo:

https://github.com/AstralUniverse1/bank-gitops

That repo owns the Helm chart, ArgoCD Application, and manual image promotion workflow.
