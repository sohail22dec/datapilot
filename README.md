# 🚀 DataPilot

DataPilot is a modern full-stack AI application powered by **Next.js 16**, **FastAPI**, **LangChain**, and **Google Gemini AI**. It provides an intelligent AI assistant paired with a high-performance backend and a modern React 19 / TypeScript frontend.

---

## 🛠 Tech Stack

### **Backend**
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12+)
- **LLM Integration:** [LangChain](https://www.langchain.com/) (`langchain-google-genai`)
- **AI Model:** Google Gemini (`gemini-2.5-flash`)
- **Database:** Supabase PostgreSQL (SQLAlchemy / psycopg2)
- **Configuration & Validation:** [Pydantic v2](https://docs.pydantic.dev/) & `pydantic-settings`
- **Package Manager:** `uv`

### **Frontend**
- **Framework:** [Next.js 16](https://nextjs.org/) (App Router)
- **UI & Styling:** React 19, Tailwind CSS v4
- **Iconography & Animation:** `lucide-react`, `framer-motion`
- **Markdown & Code Highlighting:** `react-markdown`, `remark-gfm`, `rehype-highlight`
- **Language:** TypeScript
- **Package Manager:** `pnpm`

---

## 🎨 Frontend UI Features & Design Roadmap

- **Glassmorphic Dark Theme:** Sleek dark-mode aesthetic with zinc/slate panels and glowing accent highlights.
- **Collapsible Sidebar:** Access chat history, data sources, database connectivity status, and settings.
- **AI Chat Arena:** Real-time chat feed with Markdown rendering, table support, and code syntax highlighting with copy buttons.
- **Floating Prompt Bar:** Auto-expanding prompt input with quick action chips ("Query Supabase", "Analyze Data", "Write SQL").

---

## 📁 Project Structure

```text
datapilot/
├── backend/                  # FastAPI Python backend
│   ├── app/
│   │   ├── api/
│   │   │   └── endpoints.py  # API routes (/health, /api/chat)
│   │   ├── config.py         # Pydantic Settings & environment manager
│   │   ├── llm_service.py    # LangChain & Gemini AI service logic
│   │   └── schemas.py        # Pydantic request/response models
│   ├── .env                  # Environment variables & API keys (Git-ignored)
│   ├── main.py               # FastAPI entry point & CORS configuration
│   └── pyproject.toml        # Backend dependencies & configuration
│
├── frontend/                 # Next.js TypeScript frontend
│   ├── app/                  # Next.js App Router pages & components
│   │   ├── favicon.ico
│   │   ├── globals.css       # Global styles & Tailwind CSS setup
│   │   ├── layout.tsx        # Root HTML layout
│   │   └── page.tsx          # Main application page
│   ├── public/               # Static assets & icons
│   ├── package.json          # Frontend scripts & dependencies
│   └── tsconfig.json         # TypeScript configuration
│
├── .gitignore                # Root Git ignore rules
└── README.md                 # Project documentation
```

---

## ⚡ Quick Start

### 1. Prerequisites
- **Node.js** (v20+ recommended) & **pnpm**
- **Python** (v3.12+) & **uv** package manager

---

### 2. Backend Setup

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create the `.env` file:**
   Create a `.env` file inside `backend/` with the following variables:
   ```env
   DATABASE_URL=postgresql://user:password@host:5432/postgres
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   GROQ_API_KEY=your_groq_api_key_here
   ```

3. **Install dependencies & run the server:**
   ```bash
   uv sync
   uv run python main.py
   ```
   *The backend server will run at `http://localhost:8000`.*  
   *API documentation will be available at `http://localhost:8000/docs`.*

---

### 3. Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   pnpm install
   ```

3. **Start the development server:**
   ```bash
   pnpm dev
   ```
   *The web application will be accessible at `http://localhost:3000`.*

---

### 4. Docker Compose (Full-Stack Setup)

To run both backend and frontend in isolated containers locally:

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Fill in your Supabase, Groq, and Gemini keys in .env

# 3. Build and launch containers
docker compose up --build
```

- **Frontend:** `http://localhost:3000`
- **Backend API:** `http://localhost:8000`
- **API Documentation:** `http://localhost:8000/docs`
- **Backend Health Check:** `http://localhost:8000/health`

---

## ☁️ CI/CD & AWS Deployment

### GitHub Actions CI/CD
- **Continuous Integration ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)):** Automatically runs on all PRs and feature branches:
  - Backend: `uv sync --frozen` and `uv run pytest` (14/14 guardrail & DB tests).
  - Frontend: `pnpm lint` and Next.js standalone `pnpm build`.
  - Docker: Validates multi-stage Docker builds.
- **Continuous Deployment ([`.github/workflows/cd.yml`](.github/workflows/cd.yml)):** Automatically triggers on merge to `main`:
  - Builds production Docker images.
  - Pushes images to **Amazon ECR** tagged with commit SHA and `latest`.
  - Deploys zero-downtime rolling updates to **Amazon ECS Fargate**.

*See the [AWS Deployment Guide](deploy/aws/README.md) for full IAM and ECS setup instructions.*

---

## 📡 API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health check endpoint |
| `GET` | `/api/database/health` | Supabase database connection and schema metadata |
| `POST` | `/api/chat` | Synchronous analytical query execution |
| `POST` | `/api/chat/stream` | Real-time SSE streaming endpoint (step badges, tokens, charts) |

---

## 🔐 Environment & Security

- **Secrets Protection:** Never commit `.env` or `.env.local` files to source control.
- **Dual-Layer Guardrails:** Tier-1 deterministic input regex sanitizer (`<0.5ms`) and Tier-2 SQL injection & schema access validator.

