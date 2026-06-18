# AGENTS.md

This file defines how Codex and other coding agents should work in this repository.

## Project Goal

Build a Rubicon-inspired, doctor-facing chatbot platform using Django, React, LangGraph, LangChain, and local Docker-based open-source infrastructure.

The system is for clinician support and medical knowledge retrieval. It must not behave as an autonomous diagnostic authority or a public symptom checker.

## Required Reading

Before making changes, read:

1. `doctoer_chat.md`
2. `apps/README.md`
3. `SKILLS.md`
4. Any files directly related to the task

## Architecture Principles

- Preserve Rubicon's useful operating patterns: app separation, standard API envelope, admin screens, logs, background jobs, debug traces, prompt registry, and evaluation flows.
- Do not copy Rubicon's cloud-specific assumptions. Prefer Docker-hosted open-source resources.
- Use LangGraph for chat orchestration.
- Use LangChain around the graph for retrievers, vector stores, document loaders, text splitters, prompt templates, and output parsing.
- Keep domain logic separate from Django views and serializers.
- Keep graph nodes small, named, testable, and observable.
- Keep frontend UI practical and workflow-oriented, not marketing-like.

## Medical Safety Rules

- Never present the chatbot as replacing clinician judgment.
- Do not produce definitive diagnosis without clear evidence and context.
- Always prefer source-grounded answers with citations when RAG is used.
- Red-flag/emergency scenarios must route to urgent escalation guidance.
- Do not invent medical guidelines, contraindications, or medication doses.
- Use synthetic PHI only in tests and seed data.
- Do not expose hidden chain-of-thought. Expose graph path, node summaries, retrieved sources, and model metadata instead.

## Preferred Stack

Backend:
- Django
- Django REST Framework
- Django Admin
- Django Channels or SSE for streaming
- PostgreSQL
- Redis
- RQ or Celery
- pytest

Frontend:
- React
- Vite
- TypeScript
- A small, dense admin/debug UI

AI/RAG:
- LangGraph
- LangChain
- PostgreSQL with pgvector for MVP vector retrieval
- provider-neutral vector store adapters so a dedicated vector store can be introduced later if needed
- sentence-transformers based embedding/reranker service
- Ollama or vLLM for local LLM runtime
- MinIO for document storage

Infrastructure:
- Docker Compose first
- No hardcoded secrets
- `.env.example` required for new environment variables

## Development Workflow

For every non-trivial change:

1. Inspect existing code first.
2. Write or update tests before implementation where feasible.
3. Keep changes scoped to the requested slice.
4. Run the narrowest relevant verification command.
5. Report what was changed and what was verified.

Do not:
- introduce unrelated refactors
- hardcode credentials
- add cloud-only dependencies as required services
- remove safety checks to simplify implementation
- hide failures or claim tests pass without running them

## Automatic Handoff And Git Push

Standing user preference: after Codex changes repository files, it should finish
the turn by summarizing the changed files, running the narrowest relevant
verification, committing the scoped changes on `develop`, and pushing `develop`
to `origin` without waiting for a separate prompt.

Required sequence:

1. Review `git status --short` and identify files changed by the current task.
2. Run the narrowest relevant verification command and `git diff --check`.
3. Summarize changed files and verification results in the final response.
4. Commit only the scoped task changes with an appropriate prefix.
5. Push the `develop` branch to `origin`.
6. Report the commit hash and push result.

Stop and report instead of committing or pushing if:

- the current branch is not `develop`
- verification fails
- `git diff --check` fails
- staged files include secrets, `.env`, generated local data, caches, or PHI
- unrelated dirty files would be included in the commit
- pulling/rebasing is required to avoid overwriting remote work
- the push is rejected or requires credentials/approval

Never use destructive git commands to satisfy this workflow.

## Automatic Prompt Implementation Log

Standing user preference: after every user prompt where Codex analyzes or
changes the project, append a concise entry to
`docs/prompt_implementation_log.md`.

Each entry should include:

- timestamp and current branch
- the user's prompt or a faithful one-line summary
- files changed in that turn
- what is implemented now
- what works at runtime
- what is not implemented or remains limited
- verification commands and results
- commit/push status; report the final commit hash in the final response because
  a commit cannot reliably contain its own final hash

Write every new entry in Korean unless the user explicitly requests another
language. Preserve older entries as-is.

Keep entries append-only. Do not rewrite older entries except to fix a factual
mistake in the same turn. Do not include secrets, raw PHI, hidden
chain-of-thought, local `.env` values, logs, screenshots, or generated data.

## Backend Conventions

- Views should be thin.
- Serializers validate request shape and unsafe input.
- Domain services implement business logic.
- LangGraph nodes live in a graph-focused module and return partial state updates.
- Non-streaming admin APIs should use a standard response envelope similar to Rubicon's `stdResponse`.
- Chat streaming should include request/session/message IDs in logs.
- Each graph run should persist enough metadata to debug:
  - graph version
  - node path
  - node durations
  - retrieved source IDs
  - model name
  - prompt version
  - safety flags
  - error summaries

## Frontend Conventions

- Build the actual chat/admin tool, not a landing page.
- Provide a chat screen, document/indexing admin, logs/debug viewer, and evaluation/test query view.
- Keep screens dense, readable, and operational.
- Do not display hidden chain-of-thought.
- Display citations and confidence/safety notices clearly.

## Testing Expectations

Minimum tests:
- input validation
- red-flag routing
- no-doc fallback
- retrieval with seeded docs
- citation formatting
- graph node error handling
- log persistence
- prompt version lookup
- API envelope shape

Use Docker-backed or Supabase-backed integration tests for Postgres/pgvector/Redis once those services exist.

## Documentation Expectations

Keep these docs current:

- `doctoer_chat.md`: project kickoff prompt and roadmap
- `SKILLS.md`: project-specific coding skills/workflows
- `docs/architecture.md`: technical architecture once scaffolded
- `docs/medical_safety.md`: safety and clinical-use policy
- `docs/local_dev.md`: Docker commands and troubleshooting

## Commit Guidance

Use small commits. Suggested prefixes:

- `docs:`
- `feat:`
- `fix:`
- `test:`
- `refactor:`
- `chore:`

Never commit secrets or generated local data.
