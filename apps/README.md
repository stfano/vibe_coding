# Doctor Chat App Map

This repository keeps backend Django apps under `backend/apps`.

Milestone 2 activates the auth, logging, and chat foundations:

- `common`: shared response envelope and utilities
- `health`: local service health endpoint
- `authx`: Django auth profile extension with department and role models
- `loggingx`: API request, login, service, and chat log models
- `chat`: chat session/message models and a non-streaming no-knowledge endpoint
- `knowledge`: future document metadata and indexing jobs
- `rag`: future LangChain retrieval, citation, and prompt helpers
- `graph`: future LangGraph state, nodes, edges, and runner
- `evaluation`: future test-query and safety evaluation flows
- `adminx`: future admin-facing APIs

Do not put clinical decision logic in Django views. Keep orchestration and domain behavior in focused app modules.
