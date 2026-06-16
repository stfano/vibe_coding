# Doctor Chat Project Kickoff Prompt

> File name follows the user's requested spelling: `doctoer_chat.md`.

## Purpose

Use this prompt as the first high-quality Codex prompt when starting a new project based on the Rubicon codebase style, but rebuilt for a doctor-facing medical chatbot.

The target product is not a public self-diagnosis bot. It is a clinician-support chatbot that helps doctors or authorized medical staff ask natural-language questions, retrieve approved medical knowledge, inspect reasoning/debug traces, and manage knowledge/admin data through a Django + React application.

The system must be Docker-first and must avoid cloud-only dependencies for search, vector storage, embedding, reranking, and database services.

## First Prompt For Codex

Copy the prompt below into Codex when starting implementation.

```text
You are Codex working in a new repository. Build a doctor-facing chatbot platform inspired by the Rubicon project's structure and operating patterns, but do not copy cloud dependencies or product-specific Samsung logic blindly.

Goal:
Create a Docker-based Django + React medical chatbot application that uses LangGraph and LangChain actively. The chatbot should support RAG over medical knowledge documents, clinician-facing chat, admin management, structured logs, test/evaluation workflows, and debugging traces. Assume there is no real chatbot data yet; build ingestion paths, seed sample medical documents, and interfaces that can later accept approved hospital/clinical content.

Hard constraints:
1. Use Django/DRF for backend APIs and Django Admin for operations.
2. Use React + Vite + TypeScript for the UI.
3. Use LangGraph for the main chat workflow orchestration.
4. Use LangChain for loaders, splitters, embeddings abstraction, retrievers, prompt templates, output parsers, and tool wrappers where it adds value.
5. Use open-source Docker services instead of managed cloud AI Search or managed vector DBs.
6. Use local/open-source embeddings and reranking. Prefer a dedicated embedding/reranker service so the backend can swap models without changing graph logic.
7. Use Docker Compose for local development and for the first deployable service shape.
8. Include tests, logging, debugging, admin screens, and evaluation scaffolding from the beginning.
9. Treat medical safety as a core feature. The chatbot must not present itself as independently diagnosing or replacing clinical judgment. It should produce evidence-grounded, source-cited, clinician-support responses and should identify urgent red-flag situations.
10. Do not hardcode secrets, API keys, passwords, tokens, or PHI examples.

Reference architecture:
- backend: Django + DRF + Channels or SSE streaming
- frontend: React + Vite + TypeScript
- db: Supabase/PostgreSQL with pgvector extension for relational records and MVP vector retrieval
- vector store: pgvector for the first deployment; keep vector access behind an adapter so a dedicated vector store can be added later if scale or hybrid retrieval requires it
- cache/queue: Redis + Django RQ or Celery
- object storage: MinIO for uploaded documents
- local model runtime: Ollama for MVP or vLLM/OpenAI-compatible local server for production-like runs
- embedding/reranker service: FastAPI service using Hugging Face sentence-transformers models such as mykor/KURE-v1 for Korean retrieval and BAAI reranker family, model names controlled by env vars
- observability: structured JSON logs, request IDs, LangGraph node traces, admin-visible chat/debug logs

Project structure:
- backend/config: Django settings, urls, asgi, celery/rq config
- backend/apps/common: stdResponse-like response envelope, request parsing, pagination, permissions, common decorators
- backend/apps/authx: user, role, department, permission models similar to Rubicon alpha_auth
- backend/apps/loggingx: login/API/chat/module logs similar to Rubicon alpha_log
- backend/apps/chat: chat endpoints, session/message models, streaming response, serializer validation
- backend/apps/knowledge: document upload, source metadata, chunking jobs, vector indexing status
- backend/apps/rag: LangChain retrievers, rerankers, prompt registry, source citation formatter
- backend/apps/graph: LangGraph state, nodes, edges, error handling, graph runner
- backend/apps/evaluation: golden-set evaluation, retrieval quality tests, response safety checks
- backend/apps/adminx: admin-oriented API and Django Admin registrations
- frontend/src: chat UI, admin pages, logs/debug viewer, document upload/indexing status
- docker: Dockerfiles and compose files
- docs: architecture, prompt policy, runbook, medical safety notes

LangGraph workflow:
Define a typed graph state containing request metadata, user/session/message IDs, original query, normalized query, language, retrieved docs, citations, safety flags, graph traces, response chunks, and errors.

Initial graph nodes:
1. validate_input
2. normalize_query
3. classify_medical_intent
4. detect_red_flags
5. decide_rag_route
6. retrieve_documents
7. rerank_documents
8. synthesize_answer
9. safety_review
10. format_response
11. persist_logs

Conditional edges:
- if input invalid -> format_error_response
- if emergency/red flag -> emergency_guidance_response plus retrieved evidence if available
- if no indexed documents -> safe_no_knowledge_response
- if retrieval confidence is low -> low_confidence_response with next-step suggestions
- otherwise -> synthesize_answer -> safety_review -> format_response

Medical safety behavior:
- Say the assistant supports clinical reasoning and information retrieval; it does not replace physician judgment.
- For patient-like symptom questions, answer with triage framing, possible differentials only when supported, red flags, and recommended next clinical steps.
- Avoid definitive diagnosis unless source evidence and clinical context are sufficient.
- Always show source citations when using RAG.
- Never invent guidelines or drug dosing.
- For emergency symptoms, advise urgent/emergency care escalation.
- Keep audit logs of prompt version, graph path, retrieved document IDs, model name, safety flags, and final response metadata.

Rubicon patterns to preserve:
- A standard API response envelope for non-streaming APIs.
- Clear separation between views/API modules/domain functions.
- Admin-managed prompt templates and managed words.
- Login/API/chat/module logs.
- Debug traces by pipeline section or LangGraph node.
- RQ/Celery background jobs for indexing, evaluation, and long-running tasks.
- WebSocket or SSE streaming for chat.
- Appraisal/evaluation endpoints for test queries and answer review.
- Static prompt files or prompt registry modules, but adapt all Samsung/product prompts to medical/clinical language.

Implementation plan:
Start with a thin vertical slice, not the full system.

Milestone 1:
- Create Docker Compose with backend, frontend, Supabase/Postgres configuration, redis, minio, embedding service, and optional ollama.
- Create Django project and apps listed above.
- Add health checks and basic settings via env vars.
- Add pytest and backend formatting/linting.
- Add frontend Vite app with a minimal chat screen.

Milestone 2:
- Implement auth, standard response envelope, basic logs, chat session/message models.
- Implement a non-streaming chat endpoint returning a safe placeholder when no documents exist.
- Implement Django Admin registrations.

Milestone 3:
- Implement document upload to MinIO, text extraction for txt/md/pdf, chunking, embedding, and pgvector indexing.
- Add indexing status and admin listing.
- Seed 3 small synthetic medical knowledge docs for development only.

Milestone 4:
- Implement LangGraph chat workflow with the nodes listed above.
- Use LangChain retriever abstraction over pgvector or a provider-neutral vector index adapter.
- Add local embedding and reranking calls.
- Add citations and low-confidence behavior.

Milestone 5:
- Add streaming response, graph debug viewer, evaluation test query model, and basic safety tests.

Testing requirements:
- Unit tests for serializers, input validation, graph routing, red-flag detection, citation formatting, and no-doc response.
- Integration tests using Docker services for document ingestion and retrieval.
- Snapshot-style tests for prompt templates where useful.
- Safety tests that verify emergency symptoms do not receive casual reassurance.
- Regression tests for graph error handling and logging.

Deliverables for the first implementation turn:
1. Repository scaffold.
2. Docker Compose files.
3. Backend and frontend boot successfully.
4. Health endpoint passes.
5. Minimal chat UI can call backend.
6. `docs/architecture.md`, `docs/medical_safety.md`, and `docs/local_dev.md`.
7. Tests for the first thin slice.

Before editing:
- Read AGENTS.md and SKILLS.md.
- Inspect the current repo, if any.
- Make a short implementation plan.
- Use small commits or clearly separated patches.
- Do not introduce unrelated refactors.
```

## Recommended Implementation Direction

### Build It As A Rubicon-Inspired System, Not A Fork

The current Rubicon project has useful patterns: Django apps, `stdResponse`-style envelopes, admin-managed data, logs, RQ jobs, RAG pipeline stages, prompt modules, and debug traces. The new project should reuse those ideas, not copy the product-specific code.

The biggest architectural difference should be this:

- Rubicon: custom `RubiconChatFlow.run()` orchestrates everything manually.
- Doctor Chat: LangGraph should own the workflow state, node execution, conditional routing, streaming, retries, and traceability.

LangGraph is a strong fit because its `StateGraph` model is built around nodes reading/writing shared state and edges controlling flow. LangChain is useful around the graph: document loaders, splitters, vector store adapters, retrievers, prompt templates, and output parsers.

References:
- LangGraph graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
- LangGraph `StateGraph` reference: https://reference.langchain.com/python/langgraph/graph/state/StateGraph
- LangChain retrievers: https://docs.langchain.com/oss/python/integrations/retrievers/index
- Supabase vector indexes: https://supabase.com/docs/guides/ai/vector-indexes/hnsw-indexes
- Docker Compose quickstart: https://docs.docker.com/compose/gettingstarted/

### Recommended Service Layout

| Service | Purpose |
| --- | --- |
| `backend` | Django/DRF API, admin, graph runner, auth, logs |
| `frontend` | React/Vite chat and admin UI |
| `postgres` | relational DB and MVP pgvector retrieval store |
| `redis` | cache, session state, job broker |
| `minio` | local S3-compatible document storage |
| `embedding-service` | local embeddings/reranking over sentence-transformers |
| `ollama` or `vllm` | local LLM runtime |
| `worker` | background indexing/evaluation jobs |

### Data Model Sketch

| Area | Models |
| --- | --- |
| Auth/Admin | `User`, `Department`, `Role`, `MenuPermission` |
| Chat | `ChatSession`, `ChatMessage`, `GraphRun`, `GraphNodeTrace`, `ChatFeedback` |
| Knowledge | `KnowledgeSource`, `KnowledgeDocument`, `KnowledgeChunk`, `IndexJob` |
| Prompt | `PromptTemplate`, `PromptVersion`, `ManagedWord`, `SafetyRule` |
| Evaluation | `TestQuery`, `TestRun`, `RetrievalEval`, `ResponseEval` |
| Logs | `ApiLog`, `LoginLog`, `ServiceLog`, `ModuleLog` |

### Prompt Reuse Strategy

Rubicon prompt files can inspire structure, but their Samsung/product wording must be rewritten.

Reusable prompt patterns:
- language identification
- query rewrite
- context determination
- NER/entity extraction
- guardrail/safety classification
- loading/session title generation
- response formatting
- related question generation

Medical-specific replacements:
- product categories become symptoms, conditions, specialties, body systems, medications, investigations, procedures, and care settings.
- product recommendation becomes clinical information retrieval and differential-support framing.
- product guardrails become medical safety, red flags, emergency escalation, PHI handling, and hallucination prevention.

### Vibe Coding Roadmap

Use vibe coding, but keep the work bounded. Each prompt should ask Codex for one vertical slice with tests.

1. Prompt 1: scaffold Docker + backend + frontend + health checks.
2. Prompt 2: add auth/logging/admin patterns.
3. Prompt 3: add chat session/message API and minimal UI.
4. Prompt 4: add document upload, chunking, embedding, and pgvector indexing.
5. Prompt 5: add LangGraph workflow with no-doc and low-confidence responses.
6. Prompt 6: add retrieval/rerank/citation answer synthesis.
7. Prompt 7: add streaming and debug trace viewer.
8. Prompt 8: add evaluation harness and medical safety tests.

Each prompt should include:
- exact goal
- files/modules allowed to change
- tests to add first
- expected Docker command
- expected user-visible behavior
- explicit "do not implement extra features"

### Initial Quality Bar

Do not accept a chatbot that only calls an LLM. The first usable version must have:

- source-grounded answers when documents exist
- safe fallback when no documents exist
- red-flag routing
- trace logs of graph path
- citations
- test coverage for routing and safety behavior
- admin-visible document/indexing status

## Medical Safety Boundary

This project needs stronger safety rules than a shopping/product bot.

Minimum safety policy:
- No independent diagnosis claims.
- No medication dosing unless retrieved from approved source content and still presented as clinician-support information.
- No fabricated sources.
- No hidden chain-of-thought exposure; expose concise debug summaries and graph node metadata instead.
- Emergency red flags must route to urgent escalation language.
- If the system lacks knowledge, say so clearly and ask for approved documents to be indexed.
- PHI examples in tests must be synthetic.

## Suggested First Local Commands

These are target commands for the future scaffold.

```bash
docker compose up --build
docker compose exec backend python manage.py migrate
docker compose exec backend pytest
npm --prefix frontend test
```

The first implementation should make these commands real.
