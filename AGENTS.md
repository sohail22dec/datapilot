# 🤖 AGENTS.md — Agent Guidelines & Repository Instructions

Welcome to **DataPilot**. This document defines the operating rules, coding standards, environment guidelines, and architectural principles for AI agents working in this repository.

---

## 🧭 Project Overview

**DataPilot** is a full-stack AI-driven web application featuring:
- **Backend:** FastAPI (Python 3.12+), LangChain (`langchain-google-genai`), Google Gemini 2.5 Flash, Supabase / PostgreSQL (SQLAlchemy), Pydantic v2.
- **Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, Lucide React icons, Framer Motion animations.

---

## 📁 Repository Structure & Directory Map

```text
datapilot/
├── .agents/                  # Agent skills, customizations, and workflows
├── backend/                  # Python FastAPI application
│   ├── app/
│   │   ├── api/
│   │   │   └── endpoints.py  # API route definitions
│   │   ├── config.py         # Pydantic Settings & environment variables
│   │   ├── llm_service.py    # LangChain & Gemini AI service layer
│   │   └── schemas.py        # Pydantic request/response schemas
│   ├── .env                  # Backend secrets (DO NOT COMMIT)
│   ├── main.py               # FastAPI server entry point & CORS configuration
│   ├── pyproject.toml        # Backend project metadata & dependencies
│   └── uv.lock               # uv lockfile
│
├── frontend/                 # Next.js TypeScript application
│   ├── app/                  # Next.js App Router (layout, pages, globals.css)
│   │   ├── globals.css       # Tailwind CSS v4 setup & theme styles
│   │   ├── layout.tsx        # Root layout with fonts and metadata
│   │   └── page.tsx          # Main chat & dashboard interface
│   ├── public/               # Static assets & icons
│   ├── package.json          # Frontend scripts & dependencies
│   ├── pnpm-lock.yaml        # pnpm lockfile
│   └── tsconfig.json         # TypeScript configuration
│
├── AGENTS.md                 # Agent guidelines (this file)
└── README.md                 # Project documentation & setup guide
```

---

## ⚙️ Package Managers & Execution Rules

### 1. Backend: **`uv` only**
- **Always** use `uv` for managing dependencies and running Python scripts.
- **Do not** use raw `pip install` or activate virtual environments globally without `uv`.
- Common commands:
  - Install / Sync dependencies: `uv sync`
  - Add dependency: `uv add <package-name>`
  - Run server / script: `uv run python main.py` or `uv run uvicorn main:app --reload`

### 2. Frontend: **`pnpm` only**
- **Always** use `pnpm` for frontend package management.
- **Do not** use `npm`, `yarn`, or `bun`.
- Common commands:
  - Install dependencies: `pnpm install`
  - Add dependency: `pnpm add <package-name>` (or `pnpm add -D <package-name>` for dev)
  - Run development server: `pnpm dev`
  - Build project: `pnpm build`
  - Linting: `pnpm lint`

---

## 🐍 Backend Guidelines (FastAPI & Python)

1. **Architecture & Separation of Concerns:**
   - **Routes/Endpoints:** Place all HTTP routes inside `backend/app/api/`. Keep route handlers thin; delegate business logic to services.
   - **Schemas:** Define all request and response payloads in `backend/app/schemas.py` using Pydantic v2 `BaseModel`.
   - **Settings & Config:** Access environment variables strictly via `backend/app/config.py` using `pydantic-settings`.
   - **Services:** Place LLM and database integrations in specialized modules (e.g., `app/llm_service.py`).
2. **Type Annotations & Docstrings:**
   - Use explicit Python type hints everywhere (parameters, return types, variables).
   - Write clear docstrings for all public endpoints, service functions, and helper classes.
3. **Error Handling & Logging:**
   - Use FastAPI's `HTTPException` with appropriate status codes for client errors.
   - Use standard `logging` (`logging.getLogger(__name__)`) for logging events, warnings, and errors. Avoid plain `print()` statements.
4. **LLM & AI Integrations:**
   - Always specify appropriate temperature, system instructions, and error fallbacks when interacting with Gemini / LangChain.
   - Never hardcode API keys; ensure keys come from `settings.GEMINI_API_KEY` or `settings.GROQ_API_KEY`.

---

## ⚛️ Frontend Guidelines (Next.js, React & Tailwind)

1. **Next.js App Router Conventions:**
   - Use Server Components by default.
   - Add `"use client"` directive at the very top of files only when using React hooks (`useState`, `useEffect`), browser APIs, or client event listeners.
2. **TypeScript & Strictness:**
   - Maintain strict typing. Avoid `any` — create descriptive `interface` or `type` definitions for all state, props, and API payloads.
3. **Styling & UI Aesthetics:**
   - Use **Tailwind CSS v4** utility classes for styling.
   - Design with a modern, glassmorphic dark-mode palette (zinc/slate backgrounds, glowing accents, polished borders).
   - Ensure responsive design across mobile, tablet, and desktop viewports.
   - Use `lucide-react` for consistent iconography.
4. **State Management & Data Fetching:**
   - Connect frontend API requests to backend endpoints (`http://localhost:8000/api/*`).
   - Handle loading states, empty states, and error states gracefully in UI components.

---

## 🔐 Security & Environment Rules

- **Never expose secrets:** Never commit `.env`, `.env.local`, API keys, or database credentials.
- **Git Hygiene:** Ensure `.venv`, `node_modules`, `.next`, build artifacts, and cache folders are excluded from Git commits.
- **CORS & Origin Safety:** When altering CORS settings in `main.py`, maintain safe defaults suitable for the local dev and production environments.

---

## 🧪 Testing & Verification Checklist

Before considering any task complete:
1. **Backend Verification:**
   - Ensure backend dependencies resolve with `uv sync`.
   - Verify endpoints respond as expected (e.g., test `/health` or `/api/chat`).
2. **Frontend Verification:**
   - Ensure TypeScript passes with no errors (`pnpm build` or `pnpm lint`).
   - Confirm components render cleanly and handle edge cases (empty strings, API failures).
3. **Documentation:**
   - Update `README.md` or relevant documentation if new dependencies, routes, or environment variables are introduced.
