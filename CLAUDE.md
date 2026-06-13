# CLAUDE.md

## Project

Mentora — Electron desktop course workspace for personalized learning.
Monorepo: `apps/web` (React/Vite renderer), `apps/api` (Django REST API + Celery),
`apps/desktop` (Electron host, planned).

## Commands

```bash
pnpm install                  # Install all workspace deps
pnpm infra:up                 # Start PostgreSQL, Redis, MinIO (Docker)
pnpm dev:web                  # Start Vite dev server (http://localhost:5173)
pnpm build:web                # Production build
pnpm typecheck:web            # TypeScript check
pnpm test:web                 # Run frontend tests

# API (in apps/api)
cd apps/api && python manage.py runserver   # Django dev server (http://localhost:8000)
cd apps/api && python manage.py test        # Run backend tests
cd apps/api && celery -A config worker -l info  # Celery worker
```

## Architecture

### Domain modules (Django apps under `apps/api/mentora/`)
- `courses` — course profile, knowledge scope revisions, dual-confirm activation
- `learning` — learning plans, tasks, sessions, mastery aggregation
- `assessment` — item bank, AI-generated questions, scoring, quality gates
- `knowledge` — sources, parsing, evidence, topics, retrieval (to be split)
- `agent_runtime` — workflow state machines, checkpoints, tool calls

### Infrastructure modules
- `desktop_host` — Electron main/preload, IPC, auth bridge, SSE
- `workflow_runtime` — persistent state machines, Celery tasks, leasing
- `runtime_events` — outbox pattern, recoverable SSE projections
- `model_gateway` — model routing, structured output, fallback, cost ledger

### Key constraints
- Sources belong to user library; courses reference them via versioned scopes
- `CourseProfileRevision` is immutable once confirmed; changes clone as new drafts
- `learning` cannot activate a plan independently; `courses` atomically activates both
- Model outputs are candidates only; domain services validate before persisting
- Renderer has no Node.js access; all system calls go through typed preload IPC
- No global Zustand store; use React Query for server state, local state per feature

## Tech stack
- Frontend: React 19, Vite, TypeScript (apps/web)
- Backend: Django, Django REST Framework, Celery (apps/api)
- Database: PostgreSQL + pgvector
- Cache/Queue: Redis
- Storage: MinIO (local) / COS (prod)
- Desktop: Electron (planned, apps/desktop)

## Documentation
- `docs/architecture/end-to-end-implementation-plan.md` — master implementation plan
- `docs/architecture/module-boundaries.md` — domain ownership and constraints
- `docs/architecture/technical-solution.md` — tech decisions and evolution log
- `docs/architecture/adr/` — Architecture Decision Records (5 ADRs)

## Git workflow
- Local branch: `lh` (all work happens here)
- Remote: `origin` → `https://github.com/premouseking/Mentora`
