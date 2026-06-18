# Doctor Chat

Doctor Chat is a Docker-first clinician-support chatbot platform scaffold. It is inspired by Rubicon operating patterns, but rebuilt for a local open-source stack with Django, React, LangGraph/LangChain-ready app boundaries, and medical safety constraints.

The current repository is an early vertical slice. It can run a backend health API, a minimal React workspace, Django Admin registrations, operational logging models, auth profile models, external Q&A ingestion, knowledge chunk indexing, citation-only retrieval smoke tests, and a non-streaming chat endpoint backed by a minimal non-LLM safety router.

## Clinical Safety Position

This project is for clinician support and medical knowledge retrieval. It must not act as an autonomous diagnostic authority or a public symptom checker.

Current chat behavior is intentionally conservative:

- It does not call an LLM.
- It does not perform RAG answer generation yet.
- It returns safe fallback responses when no approved documents are indexed, retrieval confidence is low, or a red-flag query is detected.
- It includes a clinician-judgment safety notice.
- It persists chat messages and chat log metadata for audit/debug work.

Future medical answer generation must be source-grounded, cite retrieved evidence, route emergency/red-flag scenarios to urgent escalation guidance, and avoid hidden chain-of-thought exposure.

## Current Project State

### Implemented

- Docker Compose stack shape for:
  - Django backend
  - React/Vite frontend
  - Supabase Postgres via `DATABASE_URL` or `SUPABASE_DATABASE_URL`
  - Redis
  - MinIO
  - FastAPI embedding-service scaffold
  - optional Ollama profile
- Django/DRF backend with:
  - standard API response envelope
  - health endpoint
  - auth profile models for department, role, and clinician metadata
  - API/login/service/chat log models
  - API request logging middleware with request IDs
  - chat session/message models
  - safe no-indexed-documents chat endpoint
  - minimal graph-compatible chat safety router with red-flag suppression and ready-document retrieval
  - HiDoc answer-level Q&A ingestion into `ExternalQnaRecord`
  - Q&A-to-knowledge indexing into documents/chunks/index jobs
  - knowledge document review gate for `needs_review`, `ready`, and `disabled`
  - deterministic and HTTP embedding adapter boundaries
  - citation-only chunk retrieval command and verification API
  - Django Admin registration for active models
- React/Vite frontend with:
  - backend health status panel
  - local service status panel
  - minimal chat workspace calling the backend
- Documentation:
  - `doctoer_chat.md`
  - `SKILLS.md`
  - `apps/README.md`
  - `docs/architecture.md`
  - `docs/local_dev.md`
  - `docs/medical_safety.md`
- Tests for:
  - response envelope shape
  - health API
  - auth profile model links
  - logging model behavior
  - login signal logging
  - chat API no-knowledge response and persistence
  - API request log persistence

### Not Implemented Yet

- Full LangGraph workflow execution with LLM answer synthesis
- LangChain retrievers, prompt templates, and citation formatting inside chat
- document upload and parsing
- production embedding/reranking models beyond deterministic scaffold
- prompt registry/versioning
- evaluation/golden-set workflows
- streaming chat over SSE or WebSocket
- graph debug trace viewer
- production authentication/authorization policy

## Repository Layout

```text
.
├── backend/                 # Django/DRF project
│   ├── config/              # settings, urls, ASGI/WSGI
│   └── apps/
│       ├── common/          # response envelope and shared base models
│       ├── health/          # service health API
│       ├── authx/           # department, role, user profile
│       ├── loggingx/        # API/login/service/chat logs
│       ├── chat/            # chat session/message API and services
│       ├── knowledge/       # external Q&A ingestion and knowledge indexing
│       ├── rag/             # embedding adapters and citation-only retrieval helpers
│       ├── graph/           # future LangGraph workflow
│       ├── evaluation/      # future evaluation flows
│       └── adminx/          # future admin-facing APIs
├── frontend/                # React + Vite + TypeScript UI
├── embedding-service/       # FastAPI scaffold for embeddings/reranking
├── docs/                    # architecture, safety, local dev notes
├── apps/README.md           # app map
├── doctoer_chat.md          # project kickoff prompt and roadmap
├── SKILLS.md                # repo-local working agreements
└── docker-compose.yml       # local open-source service stack
```

## API Surface

### `GET /api/health/`

Returns the standard response envelope with backend status and configured dependency metadata.

### `POST /api/chat/messages/`

Request:

```json
{
  "message": "Can you answer from approved local documents?",
  "session_id": null
}
```

Current response behavior:

- validates request shape
- creates or reuses a chat session
- persists the user message
- executes a minimal graph-compatible safety router
- searches only `ready` knowledge documents
- suppresses red-flag queries before retrieval
- persists an assistant safety-router response
- writes a chat log
- returns source status, safety flags, citations, graph path, node summaries, and `graph.executed: true`

## Local Development

Create a local environment file:

```bash
cp .env.example .env
```

Review the copied `.env` before starting services. Do not commit real secrets, access tokens, PHI, or machine-specific credentials.

Set `DATABASE_URL` or `SUPABASE_DATABASE_URL` to a Supabase Postgres connection string for shared development or deployment. Leave both empty to use the backend's local SQLite fallback.

Start the stack:

```bash
docker compose up --build
```

Run database migrations:

```bash
docker compose exec backend python manage.py migrate
```

Create an admin user:

```bash
docker compose exec backend python manage.py createsuperuser
```

Main URLs:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/api/health/
- Chat API: http://localhost:8000/api/chat/messages/
- Django Admin: http://localhost:8000/admin/
- MinIO console: http://localhost:9001
- Embedding service health: http://localhost:8080/health

Optional local LLM runtime:

```bash
docker compose --profile llm up ollama
```

## Verification

Backend tests:

```bash
cd backend
python -m pip install -r requirements.txt
pytest
```

Frontend build:

```bash
npm --prefix frontend install
npm --prefix frontend run build
```

Docker-based backend tests:

```bash
docker compose exec backend pytest
```

## HiDoc Q&A Ingestion

The backend includes a Django management command for collecting answer-level
HiDoc Q&A records into the configured database. In Supabase-backed runs, set
`DATABASE_URL` or `SUPABASE_DATABASE_URL`, run migrations, then run ingestion.
Progress is appended to `ingestion.log` and can be watched with `tail -f`.

Pediatric 100-record sample:

```bash
cd backend
python manage.py migrate
python manage.py ingest_hidoc_qna --department 소아과 --limit 100 --workers 5 --mode sample
```

Full department collection:

```bash
cd backend
python manage.py ingest_hidoc_qna --all --workers 10 --mode full
```

Monitor progress:

```bash
tail -f ingestion.log
```

Useful safe verification command:

```bash
cd backend
python manage.py ingest_hidoc_qna --department 소아과 --limit 5 --workers 2 --mode sample --dry-run --max-pages 1 --skip-total-discovery
```

The command stores one row per question/answer pair in
`knowledge_externalqnarecord`. Deduplication is based on the stable external ID
`hidoc:<question_id>:<answer_id>`; repeated runs update the same row rather than
creating duplicates. A separate `content_hash` tracks changes to title,
question, and answer content.

HiDoc content is third-party medical Q&A content. Treat it as a candidate or
evaluation corpus unless explicit source permission covers ingestion, storage,
embedding, RAG use, citations, and deployment.

## Knowledge Indexing And Retrieval Smoke Test

After the pediatric sample exists in `knowledge_externalqnarecord`, index those
100 rows into knowledge documents/chunks:

```bash
cd backend
python manage.py index_external_qna --source hidoc --department-code PD000 --limit 100
```

Run citation-only retrieval:

```bash
cd backend
python manage.py search_knowledge --query "아기 고환 물집 아기띠" --top-k 5 --source hidoc --department-code PD000
```

By default, retrieval only uses `ready` documents. HiDoc documents are indexed as
`needs_review`, so they must be explicitly reviewed before default retrieval can
return them. Admin verification can include review-pending documents with:

```bash
cd backend
python manage.py search_knowledge --query "아기 고환 물집 아기띠" --top-k 5 --source hidoc --department-code PD000 --include-needs-review
```

The search command and verification API return previews and citation metadata.
They do not call an LLM and do not generate medical advice. Re-running
`index_external_qna` is idempotent: the same document rows are updated and their
chunks are replaced, so duplicate chunks are not created. Existing `ready` or
`disabled` review status is preserved unless source content changes; changed
ready content is reset to `needs_review`.

Review and verification API surface:

- `GET /api/knowledge/documents/`
- `GET /api/knowledge/documents/<id>/`
- `PATCH /api/knowledge/documents/<id>/status/`
- `GET /api/knowledge/search/verify/`

## Development Rules

Before making non-trivial changes, read:

1. `doctoer_chat.md`
2. `apps/README.md`
3. `SKILLS.md`
4. files directly related to the task

Keep domain logic out of Django views. Use serializers for request validation, domain services for business behavior, and graph-focused modules for future LangGraph nodes.

Non-streaming admin/API responses should use the standard envelope from `backend/apps/common/responses.py`. Chat streaming may use a different event format later, but must include request/session/message IDs in logs.

When adding medical RAG behavior:

- use citations for retrieved medical claims
- do not invent sources, contraindications, or medication doses
- route red flags to urgent escalation guidance
- expose graph path, node summaries, retrieved source metadata, model metadata, prompt version, and safety flags
- do not expose hidden chain-of-thought

## Next Practical Milestones

1. Add an evaluation dataset and retrieval metrics for ready documents.
2. Promote a small reviewed subset of synthetic or approved documents to `ready`.
3. Compare deterministic embeddings with the HTTP Korean embedding service.
4. Add prompt registry and source-grounded LLM synthesis only after retrieval and safety metrics are stable.
5. Add streaming chat and an operational debug/log viewer in the frontend.

## Security Note

Environment files must not contain committed real credentials. If token-like values are found in tracked files, rotate them and replace them with placeholders before sharing or deploying the repository.
