# Doctor Chat App Map

This repository keeps backend Django apps under `backend/apps`.

Milestone 2 activated the auth, logging, and chat foundations. The current slice also includes review-gated knowledge retrieval, source-grounded synthesis, and evaluation smoke workflows:

- `common`: shared response envelope and utilities
- `health`: local service health endpoint
- `authx`: Django auth profile extension with department and role models
- `loggingx`: API request, login, service, and chat log models
- `chat`: chat session/message models and a non-streaming graph-backed endpoint
- `knowledge`: external Q&A records, document/chunk indexing, review gates, and retrieval verification APIs
- `rag`: embedding adapters, retrieval helpers, citation metadata, and local LLM adapters
- `graph`: minimal graph-compatible safety router with ready-document retrieval and source-grounded synthesis
- `evaluation`: golden-set chat/RAG smoke datasets, runs, results, and read-only APIs
- `adminx`: future admin-facing APIs

Do not put clinical decision logic in Django views. Keep orchestration and domain behavior in focused app modules.
