# Architecture

## Runtime

`Browser/PWA → FastAPI → SQLAlchemy → SQLite/PostgreSQL`

`Camera → private upload → safe image normalization → GeminiService → structured AIResult → teacher review → StudentScore`

## Layers

- `app/main.py` — HTTP routes and workflow orchestration.
- `app/models.py` — normalized persistence.
- `app/schemas.py` — request/response and AI validation schemas.
- `app/services.py` — score engine, ranking, attendance, identity matching, image normalization, mistake memory and audit.
- `app/ai_service.py` — single Gemini integration boundary.
- `app/static/` — responsive PWA UI, live camera and mobile camera fallback.
- `alembic/` — database migrations.

## Design decisions

### Empty-first
Academic data is teacher-created. There are no invented student records or scores.

### Camera-first identity
The teacher does not identify the student before scanning. The paper provides identity evidence. The backend performs deterministic class-scoped matching after AI extraction.

### Fast attendance
P/A circular controls save on tap. Date is part of the attendance record. One student/day is unique.

### Single source of truth
`StudentScore` is authoritative for assessment marks. AI suggestions are stored separately until teacher review resolves them.

### Offline attendance
The browser uses IndexedDB as a temporary retry queue for failed attendance writes. The backend remains authoritative.

## Production path

PostgreSQL + private object storage + background job queue + stronger auth/SSO + rate limiting + monitoring + durable conflict resolution + real-device E2E tests + calibrated AI evaluation benchmark.
