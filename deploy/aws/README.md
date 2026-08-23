# ☁️ AWS ECS Fargate & ECR Deployment Guide for DataPilot

This guide explains how to deploy **DataPilot** to Amazon Web Services using **Amazon ECR** (Elastic Container Registry) and **Amazon ECS Fargate** with automated **GitHub Actions CI/CD**.

---

## 📋 Prerequisites & Architecture

- **Amazon ECR:** Two private repositories (`datapilot-backend` and `datapilot-frontend`) to store Docker container images.
- **Amazon ECS:** An ECS Cluster running **Fargate** (serverless containers) with an Application Load Balancer (ALB).
- **External Services:** 
  - Supabase PostgreSQL database.
  - Groq & Google Gemini APIs.

---

## 🛠️ Step-by-Step AWS Setup

### 1. Create Amazon ECR Repositories

In the AWS Console (or via AWS CLI), create two private repositories in your desired region (e.g. `us-east-1` or `ap-south-1`):

```bash
# Create Backend ECR Repository
aws ecr create-repository \
    --repository-name datapilot-backend \
    --image-scanning-configuration scanOnPush=true \
    --region us-east-1

# Create Frontend ECR Repository
aws ecr create-repository \
    --repository-name datapilot-frontend \
    --image-scanning-configuration scanOnPush=true \
    --region us-east-1
```

---

### 2. Create IAM User & Permissions for GitHub Actions

Create an IAM User for GitHub Actions (e.g., `github-actions-datapilot`) with the following policies:
- `AmazonEC2ContainerRegistryPowerUser` (for pushing images to ECR)
- `AmazonECS_FullAccess` (or scoped permissions to update the ECS service)

Generate an **Access Key ID** and **Secret Access Key**.

---

### 3. Store Database & AI Secrets in AWS Secrets Manager

Store your production secrets in AWS Secrets Manager:
- `datapilot/DATABASE_URL` $\rightarrow$ `postgresql://postgres:...`
- `datapilot/GROQ_API_KEY` $\rightarrow$ `gsk_...`
- `datapilot/GEMINI_API_KEY` $\rightarrow$ `AIzaSy_...`

Ensure your ECS task execution role (`ecsTaskExecutionRole`) has `secretsmanager:GetSecretValue` permission.

---

### 4. Configure GitHub Repository Secrets

In your GitHub repository, navigate to **Settings $\rightarrow$ Secrets and variables $\rightarrow$ Actions** and add the following repository secrets:

| Secret Name | Description | Example Value |
| :--- | :--- | :--- |
| `AWS_ACCESS_KEY_ID` | AWS IAM Access Key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM Secret Key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | AWS Region | `us-east-1` |
| `ECR_BACKEND_REPOSITORY` | ECR repo for backend | `datapilot-backend` |
| `ECR_FRONTEND_REPOSITORY` | ECR repo for frontend | `datapilot-frontend` |
| `ECS_CLUSTER` | Name of your ECS Cluster | `datapilot-cluster` |
| `ECS_SERVICE` | Name of your ECS Service | `datapilot-service` |
| `NEXT_PUBLIC_BACKEND_URL` | Public backend URL / ALB URL | `https://api.yourdomain.com` |

---

### 5. Automated CI/CD Execution Flow

1. **On Pull Request / Push to Feature Branches (`.github/workflows/ci.yml`):**
   - Runs backend test suite via `uv run pytest`.
   - Runs frontend linter and standalone Next.js build via `pnpm`.
   - Verifies Docker builds.
2. **On Merge to `main` (`.github/workflows/cd.yml`):**
   - Authenticates with AWS.
   - Builds & tags production Docker images with commit SHA and `latest`.
   - Pushes images to Amazon ECR.
   - Deploys updated task definition to Amazon ECS Fargate with zero downtime rolling updates.
