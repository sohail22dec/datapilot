# 🚀 AWS EC2 (m7i-flex.large) + Amazon ECR Auto-Deployment Guide

This architecture is optimized for **AWS EC2 (e.g. `m7i-flex.large` or similar)** with **Amazon ECR** to ensure blazing-fast, zero-downtime automated deployments.

---

## 💡 Why this architecture is optimal

- **Fast & Isolated Builds:** 
  1. **GitHub Actions (16 GB RAM)** builds the Docker images in the cloud with layer caching.
  2. **Amazon ECR** stores and versions your ready-to-run images.
  3. **Your EC2 Instance (`m7i-flex.large`)** simply downloads the finished images and restarts containers in **under 10 seconds** without CPU or build lockups.

---

## 🏗️ Architecture Diagram

```text
[ Developer Machine ]
        │
        ▼ git push origin main
[ GitHub Actions Cloud (16 GB RAM) ]
   ├── 1. Runs pytest & builds Next.js
   ├── 2. Builds Docker images & pushes to Amazon ECR
   └── 3. Connects to EC2 (m7i-flex.large) via SSH
            │
            ▼
[ AWS EC2 (m7i-flex.large) ]
   ├── Pulls pre-built images from Amazon ECR
   ├── Starts containers:
   │    ├── Frontend (Next.js 16) → http://<EC2-IP>:3000
   │    └── Backend (FastAPI)    → http://<EC2-IP>:8000
   └── Verifies health status ✅
```

---

## 🛠️ Step-by-Step Setup Guide

### 1. Create Amazon ECR Repositories (One-Time)

In the AWS Console (or AWS CLI), create two private ECR repositories in your region (`ap-southeast-2`):

```bash
# Create Backend ECR Repository
aws ecr create-repository --repository-name datapilot-backend --region ap-southeast-2

# Create Frontend ECR Repository
aws ecr create-repository --repository-name datapilot-frontend --region ap-southeast-2
```

---

### 2. Configure Inbound Security Group on EC2

Ensure your EC2 Security Group allows:
- **SSH (Port 22)**: `0.0.0.0/0`
- **HTTP (Port 80)**: `0.0.0.0/0`
- **Port 3000 (Frontend)**: `0.0.0.0/0`
- **Port 8000 (Backend API)**: `0.0.0.0/0`

---

### 3. One-Time Setup on your EC2 Instance

Connect to your EC2 instance from your computer:
```bash
ssh -i /path/to/your-key.pem ubuntu@<YOUR-EC2-PUBLIC-IP>
```

Run these commands inside EC2:

```bash
# 1. Install Docker & Docker Compose
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git curl
sudo usermod -aG docker ubuntu && newgrp docker

# 2. Clone your GitHub repository
cd /home/ubuntu
git clone https://github.com/<YOUR-GITHUB-USERNAME>/datapilot.git
cd datapilot

# 3. Create production .env file
cp backend/.env.example backend/.env
nano backend/.env  # (paste your Supabase DB, Gemini, and Groq API keys)
```

---

### 4. Configure GitHub Repository Secrets (One-Time)

In your GitHub repository, go to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions** and add these secrets:

| Secret Name | Description | Example Value |
| :--- | :--- | :--- |
| `AWS_ACCESS_KEY_ID` | IAM user access key with ECR access | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret access key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | AWS Region where ECR is hosted | `us-east-1` |
| `ECR_BACKEND_REPOSITORY` | Backend ECR repo name | `datapilot-backend` |
| `ECR_FRONTEND_REPOSITORY` | Frontend ECR repo name | `datapilot-frontend` |
| `EC2_HOST` | Public IP address of your EC2 | `54.210.123.45` |
| `EC2_USERNAME` | EC2 username | `ubuntu` |
| `EC2_SSH_KEY` | Full content of your `.pem` key file | `-----BEGIN RSA PRIVATE KEY----- ...` |

---

## 🎉 How It Deploys From Now On

Whenever you push to GitHub:
```bash
git add .
git commit -m "New update"
git push origin main
```

1. **GitHub Actions** tests your code, builds the container images on GitHub's 16 GB servers, and pushes them to **Amazon ECR**.
2. **GitHub Actions** SSHs to your `t3.micro` instance, tells it to pull the pre-built images from ECR, and starts them with `docker compose up -d`.
3. Your server updates in **under 15 seconds** with **zero lag or memory crashes**!
