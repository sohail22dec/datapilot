# 🚀 AWS EC2 (t3.micro) + Amazon ECR Auto-Deployment Guide

This architecture is specially optimized for **AWS `t3.micro` (1 GB RAM)** instances to prevent CPU/RAM crashes during builds while keeping your deployments 100% automated.

---

## 💡 Why this architecture is best for `t3.micro`

- **The Problem with 1 GB RAM:** Next.js and Python compilation require **1.5 GB - 2 GB of RAM**. If you build code directly on a `t3.micro`, the server runs out of memory (OOM) and freezes or crashes your website.
- **The Solution:** 
  1. **GitHub Actions (16 GB RAM)** builds the Docker images in the cloud for free.
  2. **Amazon ECR** stores your ready-to-run images.
  3. **Your `t3.micro`** only downloads the finished images and starts them in **under 10 seconds** with **< 5% CPU and ~300 MB RAM**.

---

## 🏗️ Architecture Diagram

```text
[ Developer Machine ]
        │
        ▼ git push origin main
[ GitHub Actions Cloud (16 GB RAM) ]
   ├── 1. Runs pytest & builds Next.js
   ├── 2. Builds Docker images & pushes to Amazon ECR
   └── 3. Connects to EC2 (t3.micro) via SSH
            │
            ▼
[ AWS EC2 (t3.micro) ]
   ├── Pulls pre-built images from Amazon ECR (0% build stress)
   ├── Starts containers:
   │    ├── Frontend (Next.js 16) → http://<EC2-IP>:3000
   │    └── Backend (FastAPI)    → http://<EC2-IP>:8000
   └── Verifies health status ✅
```

---

## 🛠️ Step-by-Step Setup Guide

### 1. Create Amazon ECR Repositories (One-Time)

In the AWS Console (or AWS CLI), create two private ECR repositories in your region (e.g. `us-east-1`):

```bash
# Create Backend ECR Repository
aws ecr create-repository --repository-name datapilot-backend --region us-east-1

# Create Frontend ECR Repository
aws ecr create-repository --repository-name datapilot-frontend --region us-east-1
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
