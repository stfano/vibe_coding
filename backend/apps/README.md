# Backend Apps

Milestone 2 keeps chatbot behavior deliberately narrow while adding operational foundations.

Active APIs:

- `GET /api/health/`
- `POST /api/chat/messages/`

Active model areas:

- `authx`: `Department`, `Role`, `UserProfile`
- `loggingx`: `ApiRequestLog`, `LoginEventLog`, `ServiceLog`, `ChatLog`
- `chat`: `ChatSession`, `ChatMessage`
- `knowledge`: `ExternalQnaRecord`, `KnowledgeSource`, `KnowledgeDocument`, `KnowledgeChunk`, and `IndexJob` for answer-level external Q&A ingestion and chunk indexing
- `knowledge`: review-gate APIs for document list/detail/status updates and retrieval verification
- `rag`: embedding adapters and citation-only knowledge chunk retrieval, defaulting to ready documents only
- `graph`: minimal chat safety router for validation, red-flag suppression, ready-document retrieval, source-status decisions, and graph metadata

Future app shells remain:

- `evaluation`
- `adminx`

Views should stay thin. Domain logic should live in service modules, graph logic in `graph`, and retrieval/prompt/citation helpers in `rag`.
