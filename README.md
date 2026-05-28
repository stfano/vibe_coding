# Doctor Chat

Doctor Chat is a Docker-first clinician-support chatbot platform scaffold. It is inspired by Rubicon operating patterns, but rebuilt for a local open-source stack with Django, React, LangGraph/LangChain-ready app boundaries, and medical safety constraints.

The current repository is an early vertical slice. It can run a backend health API, a minimal React workspace, Django Admin registrations, operational logging models, auth profile models, and a non-streaming chat endpoint that safely returns a no-knowledge response because no approved medical documents are indexed yet.

## Clinical Safety Position

This project is for clinician support and medical knowledge retrieval. It must not act as an autonomous diagnostic authority or a public symptom checker.

Current chat behavior is intentionally conservative:

- It does not call an LLM.
- It does not perform RAG retrieval yet.
- It returns a safe no-knowledge response when no approved documents are indexed.
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
  - Qdrant
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

- LangGraph workflow execution
- LangChain retrievers, prompt templates, and citation formatting
- document upload, parsing, chunking, and indexing
- Qdrant retrieval
- embedding/reranking endpoints beyond health scaffold
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
│       ├── knowledge/       # future document/indexing app
│       ├── rag/             # future LangChain retrieval helpers
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
- persists an assistant no-knowledge message
- writes a chat log
- returns no citations and `graph.executed: false`

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
- Qdrant dashboard: http://localhost:6333/dashboard
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

1. Add knowledge document models, upload API, and indexing job status.
2. Implement text extraction/chunking for approved synthetic documents.
3. Add embedding-service `/embed` and optional `/rerank` endpoints.
4. Wire Qdrant indexing and retrieval behind backend services.
5. Implement LangGraph state, nodes, conditional routing, and graph-run metadata.
6. Add citation formatting, low-confidence behavior, and red-flag routing tests.
7. Add streaming chat and an operational debug/log viewer in the frontend.

## Security Note

Environment files must not contain committed real credentials. If token-like values are found in tracked files, rotate them and replace them with placeholders before sharing or deploying the repository.
