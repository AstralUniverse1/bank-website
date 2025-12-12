# Bank Website – Flask, Docker, Terraform, GitHub Actions, Kubernetes

A simple banking web app with:
- Flask backend (SQLite)
- HTML/CSS/JS frontend
- Docker containerization
- Kubernetes deployment
- GitHub Actions for CI and Terraform automation
- Terraform for provisioning an AWS EC2 instance (ap-northeast-1)

File system:

backend/        – Flask app + local SQLite DB

frontend/       – Static UI

Terraform/      – EC2 instance (ap-northeast-1)

k8s/            - Deployment with NodePort

.github/workflows/ci.yml         - CI pipeline (lint, build, scan, push)

.github/workflows/terraform.yml  - Terraform pipeline (init + apply)

Dockerfile      – Builds and runs the application

Run locally with Docker:
1) docker build -t bank-app .
2) docker run -p 5000:5000 bank-app
3) Open http://127.0.0.1:5000

Kubernetes
1) kubectl apply -f k8s/
2) (Once pod is running) kubectl get svc bank-app
3) Open http://<NODE_IP>:<NODEPORT>

CI pipeline (ci.yml):
- Lints Dockerfile (hadolint)
- Builds Docker image
- Scans the image with Trivy
- Runs a simple smoke test (container starts and logs checked)
- Pushes image to DockerHub (latest + commit SHA tag)

Terraform pipeline (terraform.yml):
1) terraform init
2) terraform apply -auto-approve (manual workflow run. emphemeral state - destroy manually in console)
