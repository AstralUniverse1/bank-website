# DevOps Project
* Demo banking web app used to showcase Docker, CI/CD and Terraform
* Flask backend (on port 5000), HTML/CSS/JS frontend, SQLite database (single-replica)
* Includes docker compose setup with persistent volume
## CI/CD
* GitHub Actions (requires repo/fork Actions secrets: DOCKER_USERNAME, DOCKER_PASSWORD)
* CI workflow: lint, build, trivy, test, docker push
## Infrastructure
* Terraform workflow creates remote state in AWS S3 bucket + DynamoDB
* Requirements: AWS_REGION, TF_LOCK_TABLE, TF_STATE_BUCKET, TF_VAR_key_name, TF_VAR_ssh_cidr, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
* Provisions EC2 + SG (port 22 and 80 inbound)
* Ansible configures EC2 (docker + compose install only)
## Kubernetes & GitOps
* Deploys to the cluster selected by the active kubectl context
* Stateless Kubernetes deployment
* NodePort service
* Helm: Stateful MySQL (StatefulSet + PVC; requires a default StorageClass)
* ArgoCD