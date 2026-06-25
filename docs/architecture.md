# Doctor Chat Architecture

Milestone 2 established the local development shape and the first backend operating patterns. The current slice adds review-gated knowledge retrieval, source-grounded local answer synthesis, and a deterministic evaluation workflow.

## Services

- `backend`: Django and DRF API service.
- `frontend`: React, Vite, and TypeScript clinician workspace shell.
- `supabase postgres`: managed Postgres for deployed or shared environments, configured through `DATABASE_URL` or `SUPABASE_DATABASE_URL`.
- `redis`: future cache and background job broker.
- `minio`: future S3-compatible document storage.
- `embedding-service`: FastAPI service with health, `/embed`, and `/rerank` contract. It can use sentence-transformers for semantic embeddings when available and keeps deterministic fallback for tests and offline local runs.
- `ollama`: optional local LLM runtime behind the `llm` Compose profile.

MVP vector retrieval should use Supabase/Postgres with `pgvector`. This keeps
document metadata, chunk rows, embeddings, indexing status, chat logs, and
evaluation records in one managed database for the first deployment. If corpus
size, filtered vector recall, hybrid retrieval, or independent vector scaling
becomes a bottleneck, add a dedicated vector store behind a provider-neutral
vector index adapter.

## Backend App Boundaries

Active APIs:

- `apps.health`: `GET /api/health/`
- `apps.chat`: `POST /api/chat/messages/`
- `apps.knowledge`: document review list/detail/status APIs and retrieval verification.
- `apps.evaluation`: dataset and run read-only APIs.

Active model apps:

- `apps.authx`: Django auth extension via `Department`, `Role`, and `UserProfile`.
- `apps.loggingx`: API request, login, service, and chat logs.
- `apps.chat`: chat session and message persistence.
- `apps.knowledge`: external Q&A records, knowledge sources, documents, chunks, and index jobs.
- `apps.rag`: embedding adapter boundary, retrieval service, and local chat LLM adapters.
- `apps.graph`: LangGraph `StateGraph` chat safety/RAG workflow.
- `apps.evaluation`: golden-set chat/RAG smoke datasets, runs, and results.

Non-streaming APIs should use the standard response envelope in `apps.common.responses`.

The chat endpoint executes a LangGraph `StateGraph` safety/RAG workflow. It
validates input, suppresses red-flag queries before retrieval, searches only
`ready` documents, chooses a source status, synthesizes a source-grounded answer
only when source status is `retrieved`, and persists graph metadata.

## Database Configuration

The backend prefers a Postgres connection string in `DATABASE_URL`, falling back to `SUPABASE_DATABASE_URL`. This is intended for Supabase Postgres in deployment. If neither variable is set, the backend uses local SQLite for early development and unit tests.

The local Docker Compose stack no longer starts a Postgres or vector database container.
It keeps local open-source services for Redis, MinIO, embedding service, and
optional Ollama. SQLite can support non-RAG local work, but vector indexing and
retrieval require a Postgres database with the `pgvector` extension, such as
Supabase Postgres.

## External Q&A Indexing Slice

HiDoc sample ingestion stores answer-level rows in `ExternalQnaRecord`. The
`index_external_qna` management command converts those rows into
`KnowledgeDocument` and `KnowledgeChunk` records, stores citation metadata, and
records each run in `IndexJob`. The first supported retrieval surface is the
`search_knowledge` management command, which returns chunk previews and
citations only.

Use deterministic embeddings for repeatable tests and offline fallback. Use the
HTTP embedding adapter when `EMBEDDING_PROVIDER=http` and
`EMBEDDING_SERVICE_URL` points at a running embedding service. Retrieval
verification returns embedding transport, provider, model, dimensions, vector
metric, fallback state, and raw score metadata so operators can tell whether a
search used deterministic fallback or semantic embeddings.

Retrieval is gated by document review status. Default retrieval includes only
`KnowledgeDocument.status = ready`; `needs_review` can be included only in admin
verification mode, and `disabled` is always excluded. Verification endpoints and
commands return snippets, scores, and citation metadata only. They do not call
an LLM or synthesize medical guidance.

## Chat Safety Router Slice

`apps.graph.router` is the stable public entrypoint for chat orchestration, and
delegates execution to a compiled LangGraph `StateGraph` workflow in
`apps.graph.workflow`. The graph uses typed state from `apps.graph.state` and
small node functions from `apps.graph.nodes`.

The active nodes are:

- `validate_input`
- `detect_red_flags`
- `retrieve_ready_documents`
- `decide_source_status`
- `synthesize_answer`
- `safety_review`
- `format_response`
- `persist_metadata`

The workflow returns graph runtime metadata (`runtime=langgraph_stategraph`),
graph path, node summaries, source status, safety flags, citations, retrieved
source IDs, model metadata, prompt version, answer review metadata, error
summary, and `llm_executed`. Red-flag queries return urgent escalation guidance
without retrieval. No ready documents or low-confidence retrieval returns a safe
fallback. These fallback branches do not call the LLM.

Retrieval or LLM node failures are converted into a sanitized `graph_error`
branch. The response avoids raw provider exception details and keeps only a
short node-level error summary for operator debugging.

When source status is `retrieved`, the router builds a source-grounded prompt
payload containing only the user query, retrieved ready chunk text, and citation
metadata. The provider-neutral LLM adapter in `apps.rag.llms` can use Ollama for
local generation or a deterministic adapter for tests. After synthesis,
`safety_review` deterministically checks that the answer cites retrieved context
and avoids obvious unsupported diagnosis, prescription, or medication-dose
language. Failed answer review changes `source_status` to
`answer_grounding_failed`, preserves citations and retrieved source IDs for
operator debugging, and returns a safe fallback instead of the generated text.

## Out Of Scope For Milestone 2

- Production medical answer workflow beyond source-grounded local synthesis
- Document upload and parsing
- Streaming chat and graph debug UI
