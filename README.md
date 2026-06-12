# Mentora

Mentora is an Electron desktop course workspace for personalized learning.
Sources live in a reusable user library. Each course references an explicit,
versioned knowledge scope and owns its learning intents, plans, learning
events, assessments, and actionable learning map.

## Repository layout

```text
apps/
  desktop/      Target Electron main/preload host (to be implemented)
  web/          Current React/Vite renderer
  api/          Django REST API, SSE, Celery, and domain workflows
docs/
  architecture/ Architecture and module boundary documents
infra/
  docker/       Local development infrastructure
```

## Local development

1. Copy `.env.example` to `.env`.
2. Run `pnpm infra:up`.
3. Follow `apps/api/README.md` to start the API and workers.
4. Run `pnpm install`, then `pnpm dev:web`.

The current pre-Electron skeleton exposes:

- Web UI: `http://localhost:5173`
- API health check: `http://localhost:8000/api/health/`

The target product runs the React UI inside Electron. The Django API remains a
separately deployed cloud service; it is not bundled into the desktop app.

See [end-to-end-implementation-plan.md](docs/architecture/end-to-end-implementation-plan.md)
for the product architecture and implementation roadmap.

See [scope-versioning-design.md](docs/architecture/scope-versioning-design.md)
for source versions, course scope revisions, incremental impact analysis,
activation, and rollback semantics.

The corresponding proposed decision record is
[ADR-0001](docs/architecture/adr/0001-course-scope-versioning.md).

Question banks, AI-generated item review, assessment forms, scoring, and
mastery evidence are specified in
[assessment-item-bank-design.md](docs/architecture/assessment-item-bank-design.md)
and [ADR-0002](docs/architecture/adr/0002-assessment-item-lifecycle.md).

The real-time adaptive generation and automatic accuracy gate are specified in
[adaptive-ai-question-generation-design.md](docs/architecture/adaptive-ai-question-generation-design.md)
and [ADR-0003](docs/architecture/adr/0003-adaptive-ai-question-validation.md).

Course-profile review, editable learning-plan cards, and atomic course startup
are specified in
[ADR-0004](docs/architecture/adr/0004-profile-plan-confirmation.md).

The Electron process boundary, secure IPC, authentication, file upload, and
desktop release strategy are specified in
[desktop-client-architecture.md](docs/architecture/desktop-client-architecture.md)
and [ADR-0005](docs/architecture/adr/0005-electron-desktop-client.md).
