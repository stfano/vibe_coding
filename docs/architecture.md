# Doctor Chat Architecture

Milestone 2 establishes the local development shape and the first backend operating patterns.

## Services

- `backend`: Django and DRF API service.
- `frontend`: React, Vite, and TypeScript clinician workspace shell.
- `postgres`: relational database using the pgvector image for future vector fields.
- `redis`: future cache and background job broker.
- `qdrant`: future primary vector store.
- `minio`: future S3-compatible document storage.
- `embedding-service`: FastAPI scaffold for future sentence-transformers embeddings and reranking.
- `ollama`: optional local LLM runtime behind the `llm` Compose profile.

## Backend App Boundaries

Active APIs:

- `apps.health`: `GET /api/health/`
- `apps.chat`: `POST /api/chat/messages/`

Active model apps:

- `apps.authx`: Django auth extension via `Department`, `Role`, and `UserProfile`.
- `apps.loggingx`: API request, login, service, and chat logs.
- `apps.chat`: chat session and message persistence.

Non-streaming APIs should use the standard response envelope in `apps.common.responses`.

The chat endpoint currently returns a no-knowledge placeholder when no approved documents are indexed. It does not call an LLM and does not execute a LangGraph workflow yet.

## Out Of Scope For Milestone 2

- Medical answer generation
- RAG retrieval
- Document upload and indexing
- LangGraph workflow execution
