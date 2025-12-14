# Bank Website Demo
Demo banking web application used to showcase a **complete DevOps pipeline**:
Docker → CI → Terraform → Kubernetes → Helm → ArgoCD → Ansible.
## Application
* Flask backend
* SQLite database (single-replica)
* HTML/CSS/JS frontend
* Runs on port 5000
## CI/CD
* GitHub Actions
* Linting, Trivy scan, smoke test
* Docker image build & push
* Terraform workflow (manual trigger)
## Infrastructure
* Terraform provisions EC2
* Ansible configures EC2 (Docker install)
## Kubernetes & GitOps
* Stateless Kubernetes deployment
* NodePort service
* Helm chart: `helm/bank-app`
* ArgoCD manages deployment from `dev`
* App manifest: `argocd/bank-app.yaml`

## Limitations
* SQLite limits replicas to 1
* No persistent volume