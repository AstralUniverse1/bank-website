# DevOps Project
* Demo banking web app used to showcase Docker, CI/CD and Terraform
* Flask backend (on port 5000), HTML/CSS/JS frontend, SQLite database (single-replica)
* Includes docker compose setup with persistent volume
## CI/CD
* GitHub Actions (requires repo/fork Actions secrets: DOCKER_USERNAME, DOCKER_PASSWORD (or  DOCKER_TOKEN), AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
* CI workflow: lint, build, trivy, test, docker push (doesnt touch infra)
* Terraform workflow (manual trigger only)
## Infrastructure
* Terraform provisions EC2 and SG (keypair and ssh_cidr inputs on apply - recommended)
* Ansible configures EC2 (docker and docker compose install only, no app deployment)
## Kubernetes & GitOps
* Deploys to the cluster selected by the active kubectl context
* Stateless Kubernetes deployment
* NodePort service
* Helm: Stateful MySQL (StatefulSet + PVC; requires a default StorageClass)
* ArgoCD