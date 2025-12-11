
A simple bank website built with Flask (backend) and HTML/JS frontend.
Uses SQLite for data storage.

- backend/ – Flask application, local .db file
- frontend/ – HTML, CSS, JS files for the UI
- Terraform/ - Main state for AWS (ap-northeast-1) instance vm
- .github/workflows/ - CI and Terraform execution
- Dockerfile – containerizes the app

The application is containerized using Docker. To run locally:
1. Build the Docker image:
   docker build -t bank-app .
2. Run the container:
   docker run -p 5000:5000 bank-app
3. Open your browser at http://127.0.0.1:5000

# Bank Website – Flask, Docker, Terraform, GitHub Actions

A simple banking web app with:
- Flask backend (SQLite)
- HTML/CSS/JS frontend
- Docker containerization
- GitHub Actions for CI and Terraform automation
- Terraform for provisioning an AWS EC2 instance (ap-northeast-1)

Project structure:
backend/        – Flask app + local SQLite DB
frontend/       – Static UI
Terraform/      – EC2 instance + security group
.github/workflows/ci.yml         – CI pipeline (lint, build, scan, push)
.github/workflows/terraform.yml  – Terraform pipeline (init + apply)
Dockerfile      – Builds and runs the application

Run locally with Docker:
1) docker build -t bank-app .
2) docker run -p 5000:5000 bank-app
3) Open http://127.0.0.1:5000

CI pipeline (ci.yml) does:
- Lints Dockerfile (hadolint)
- Builds Docker image
- Scans the image with Trivy
- Runs a simple smoke test (container starts and logs checked)
- Pushes image to DockerHub (latest + commit SHA tag)

Terraform pipeline (terraform.yml) does:
- terraform init
- terraform apply -auto-approve
(workflow manual trigger only for Terraform)

Tech stack:
Python/Flask, HTML/CSS/JS, Docker, GitHub Actions, Terraform, SQLite
