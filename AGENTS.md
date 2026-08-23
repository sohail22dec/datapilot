# 🤖 AGENTS.md — Agent Guidelines & Repository Instructions

Welcome to **DataPilot**. This document defines the operating rules, coding standards, environment guidelines, and architectural principles for AI agents working in this repository.

---

## 🧭 Project Overview

**DataPilot** is an enterprise-grade, full-stack AI business intelligence and analytics platform featuring:
- **Backend:** FastAPI (Python 3.12+), LangGraph cyclic state machine (`langgraph`), LangChain (`langchain-google-genai`, `langchain-groq`), Google Gemini 2.5 Flash, Supabase PostgreSQL (SQLAlchemy & psycopg2), Pydantic v2, and dual-layer security guardrails.
- **Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, Recharts data visualization, Lucide React icons, and Radix UI primitives.

---

## 📁 Repository Structure & Directory Map

```text
datapilot/
├── .agents/                      # Agent customizations, skills, and workflows
├── backend/                      # Python FastAPI & LangGraph backend
│   ├── app/
│   │   ├── agents/               # LangGraph state machine & specialized nodes
│   │   │   ├── nodes/            # Specialized graph execution nodes
│   │   │   │   ├── __init__.py   # Node exports
│   │   │   │   ├── router_node.py    # Intent classifier (data_query, stats, email, chat)
│   │   │   │   ├── sql_node.py       # Text-to-SQL generation & execution
│   │   │   │   ├── heal_node.py      # Self-healing SQL debugger (up to 2 retries)
│   │   │   │   ├── stats_node.py     # Sandboxed business metrics engine
│   │   │   │   ├── email_node.py     # Action engine / campaign drafter (HITL)
│   │   │   │   └── synthesis_node.py # Executive summary & chart config synthesis
│   │   │   ├── __init__.py       # Workflow runner & graph compiler
│   │   │   ├── graph.py          # StateGraph definition & conditional edges
│   │   │   └── state.py          # AgentState TypedDict contract
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── endpoints.py      # REST & SSE streaming endpoints (/api/chat, /api/chat/stream)
│   │   ├── guardrails/           # Dual-layer deterministic security guardrails
│   │   │   ├── __init__.py       # Guardrail exports
│   │   │   ├── input_guard.py    # Layer 1: Pre-flight input sanitizer & injection defense (<0.5ms)
│   │   │   └── sql_guard.py      # Layer 2: Post-gen SQL validator & LIMIT enforcer
│   │   ├── tools/                # Specialized agent tool suite
│   │   │   ├── __init__.py       # Tool exports
│   │   │   ├── db_tool.py        # Read-only query execution & type sanitizer
│   │   │   ├── schema_tool.py    # Schema introspection & column sampling
│   │   │   ├── python_tool.py    # Sandboxed stats calculations (profit margin, churn, MoM)
│   │   │   └── email_tool.py     # Structured campaign & business action drafter
│   │   ├── cache.py              # In-memory TTL cache for schemas and query responses
│   │   ├── config.py             # Pydantic Settings & environment variables
│   │   ├── database.py           # Supabase connection pooling & schema metadata
│   │   ├── llm_service.py        # Service orchestrator & SSE streaming generator
│   │   └── schemas.py            # Pydantic request/response schemas & ChartConfig
│   ├── tests/                    # Automated backend test suites
│   │   ├── test_input_guard.py   # Layer 1 input guardrail tests
│   │   └── test_sql_guard.py     # Layer 2 SQL guardrail tests
│   ├── .env                      # Backend environment secrets (DO NOT COMMIT)
│   ├── main.py                   # FastAPI server entry point, CORS & lifespan pool warm-up
│   ├── pyproject.toml            # Backend dependencies & metadata
│   └── uv.lock                   # uv lockfile
│
├── frontend/                     # Next.js TypeScript frontend
│   ├── app/                      # Next.js App Router
│   │   ├── globals.css           # Tailwind CSS v4 setup & theme design tokens
│   │   ├── icon.svg              # DataPilot Pilot Delta favicon
│   │   ├── layout.tsx            # Root HTML layout & fonts
│   │   └── page.tsx              # Main analytics chat & state orchestrator
│   ├── components/               # Modular UI component tree
│   │   ├── brand/
│   │   │   └── DataPilotLogo.tsx # Stealth flight delta SVG brand mark & wordmark
│   │   ├── common/
│   │   │   └── UserAvatar.tsx    # Radix Avatar wrapper
│   │   ├── sidebar/
│   │   │   └── Sidebar.tsx       # Collapsible sidebar with conversations & profile
│   │   ├── ui/                   # Radix UI primitives (Button, Avatar, Dropdown, ScrollArea, Tooltip)
│   │   └── workspace/            # Analytics chat workspace components
│   │       ├── AssistantMessage.tsx # Response card (insights, thought process, SQL, tables)
│   │       ├── ChatComposer.tsx     # Keyboard-first prompt composer
│   │       ├── ChatWorkspace.tsx    # Message feed canvas & empty states
│   │       ├── DataChart.tsx        # Recharts visualizer (Bar, Line, Area, Donut)
│   │       └── UserMessage.tsx      # Yellow user message bubble
│   ├── lib/
│   │   └── utils.ts              # Tailwind class merging utility (clsx + twMerge)
│   ├── public/                   # Static assets & brand vectors
│   ├── types/
│   │   └── chat.ts               # TypeScript data models (Message, ChartConfig, Conversation)
│   ├── package.json              # Frontend scripts & dependencies
│   ├── pnpm-lock.yaml            # pnpm lockfile
│   └── tsconfig.json             # TypeScript configuration
│
├── specs/                        # Architecture & design specifications
│   ├── 01-datapilot-ui-design.md # UI design system & token specifications
│   ├── 02-backend-supabase-agent.md # Supabase Text-to-SQL architecture
│   ├── 03_foundation_tools_state_cache.md # Tools suite, caching & AgentState
│   └── 04_langgraph_nodes_and_graph.md    # LangGraph state machine & nodes
│
├── AGENTS.md                     # Agent guidelines (this file)
└── README.md                     # Project documentation & setup guide
```

---

## ⚙️ Package Managers & Execution Rules

### 1. Backend: **`uv` only**
- **Always** use `uv` for managing dependencies, running scripts, and executing tests.
- **Do not** use raw `pip install` or activate virtual environments globally without `uv`.
- Common commands:
  - Install / Sync dependencies: `uv sync`
  - Add dependency: `uv add <package-name>`
  - Run development server: `uv run python main.py` or `uv run uvicorn main:app --reload`
  - Run test suite: `uv run pytest`

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

## 🐍 Backend Guidelines (FastAPI, LangGraph & Security)

### 1. LangGraph State Machine Architecture
- **State Definition (`app/agents/state.py`)**: All state transitions must adhere to `AgentState`. Use `Annotated[List[...], operator.add]` for accumulated lists (e.g. `messages`, `agent_thought_trace`).
- **Graph Nodes (`app/agents/nodes/`)**:
  - `router_node.py`: Classify user query into `data_query`, `statistical_analysis`, `email_action`, or `general_chat`.
  - `sql_node.py`: Generate read-only PostgreSQL queries with cached schema context and execute via `db_tool.py`.
  - `heal_node.py`: Diagnose execution errors and rewrite queries for up to 2 self-healing retries.
  - `stats_node.py`: Execute sandboxed Python business math (`profit_margin`, `churn_rate`, `mom_growth`, `inventory_burn_rate`).
  - `email_node.py`: Draft structured business action campaigns with Human-in-the-Loop (`requires_human_approval = True`).
  - `synthesis_node.py`: Synthesize executive natural-language summaries in INR (₹) and configure visual chart recommendations (`ChartConfig`).
- **Workflow Compilation (`app/agents/graph.py`)**: Compile graphs cleanly without cyclic traps or orphaned branches.

### 2. Dual-Layer Security Guardrails
- **Layer 1: Pre-Flight Input Guardrail (`app/guardrails/input_guard.py`)**:
  - Sub-millisecond (<0.5ms) deterministic regex filtering before touching any LLM.
  - Intercepts prompt injections (`<system>`, role-switching `DAN`), secret probes (`.env`, `GEMINI_API_KEY`), and SQL mutation syntax delimiters.
  - Guarantees zero false positives for legitimate business queries (e.g. *"customers who dropped orders"*).
- **Layer 2: Post-Generation SQL Guardrail (`app/guardrails/sql_guard.py`)**:
  - Validates read-only execution (must start with `SELECT` or `WITH`).
  - Blocks mutating keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`).
  - Blocks access to sensitive/internal schemas (`auth.*`, `vault.*`, `pg_shadow`, `pg_catalog.*`).
  - Blocks multi-statement execution via unquoted semicolons.
  - Auto-injects and clamps `LIMIT` clauses (default: 50, maximum: 100).

### 3. Tool Suite & Caching
- **Tools (`app/tools/`)**:
  - Keep tools pure, typed, and isolated.
  - `db_tool.py`: Enforce `SET TRANSACTION READ ONLY;` and `SET statement_timeout = '5000ms';`. Sanitize Decimal, UUID, and date objects to JSON-serializable types.
  - `python_tool.py`: Run calculations in a sandboxed namespace with blocked system/network built-ins.
- **Caching (`app/cache.py`)**:
  - `SchemaCache`: In-memory TTL cache for database schemas (default: 1 hour).
  - `QueryCache`: In-memory TTL cache for identical user questions.

### 4. API Endpoints & Streaming
- Synchronous queries: `POST /api/chat` returns a full `ChatResponse`.
- Real-time streaming: `POST /api/chat/stream` emits Server-Sent Events (SSE) containing step badges, thinking tokens, and final payload.

---

## ⚛️ Frontend Guidelines (Next.js, React & Tailwind v4)

### 1. Next.js App Router & Component Hierarchy
- Use Server Components by default; add `"use client"` only when managing state, hooks, or client event listeners.
- **Component Breakdown (`frontend/components/`)**:
  - `brand/`: Brand mark and logo (`DataPilotLogo.tsx`).
  - `sidebar/`: Collapsible sidebar navigation with conversation history and user profile (`Sidebar.tsx`).
  - `workspace/`: Analytics workspace message feed (`ChatWorkspace.tsx`), yellow user bubble (`UserMessage.tsx`), assistant response card (`AssistantMessage.tsx`), interactive charts (`DataChart.tsx`), and prompt composer (`ChatComposer.tsx`).
  - `ui/`: Accessible UI primitives (`button`, `avatar`, `dropdown-menu`, `scroll-area`, `tooltip`).

### 2. Design System & Aesthetic Tokens
- **Palette**:
  - Canvas: Charcoal dark `#181A20`
  - Sidebar Surface: `#1E222B`
  - Cards & Composer: `#242834` (Border: `#323849`)
  - Accent / Primary: Golden Yellow `#FEC50B` / `#F4B900`
  - User Bubble: Golden Yellow `#FEC50B` with dark charcoal text `#09090B`
- **Typography & Formatting**: Clean sans-serif, bold metric highlights (e.g. **₹45,200** or **$124,500**), structured tables, and collapsible thought traces.
- **Visual Charts (`DataChart.tsx`)**: Responsive Recharts charts supporting `bar`, `line`, `area`, and `donut` configurations.

### 3. TypeScript & Data Models
- Maintain strict typing in `frontend/types/chat.ts` (`Message`, `ChartConfig`, `QueryDataRow`, `Conversation`).
- Avoid `any` types.

---

## 🔐 Security & Environment Rules

- **Never expose secrets:** Never commit `.env`, `.env.local`, API keys (`GEMINI_API_KEY`, `GROQ_API_KEY`), or database credentials (`DATABASE_URL`).
- **Git Hygiene:** Ensure `.venv`, `node_modules`, `.next`, build artifacts, and cache folders are strictly ignored in `.gitignore`.
- **CORS Safety:** Maintain safe origin configurations in `main.py`.
- **Human-in-the-Loop (HITL):** Any automated business action (such as email drafting or campaigns) must set `requires_human_approval = True`.

---

## 🧪 Testing & Verification Checklist

Before considering any backend or frontend task complete:
1. **Backend Verification:**
   - Run test suite: `uv run pytest` (verify input guardrail and SQL guardrail tests pass).
   - Verify dependencies resolve cleanly: `uv sync`.
   - Verify server startup and pool warming: `uv run python main.py`.
2. **Frontend Verification:**
   - Verify linting: `pnpm lint` (0 errors, 0 warnings).
   - Verify build: `pnpm build`.
   - Confirm UI components render cleanly across mobile and desktop viewports.
3. **Documentation:**
   - Keep `README.md`, `AGENTS.md`, and relevant specs updated whenever new routes, tools, nodes, or environment variables are added.
