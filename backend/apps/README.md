# Backend Apps

Milestone 2 keeps chatbot behavior deliberately narrow while adding operational foundations.

Active APIs:

- `GET /api/health/`
- `POST /api/chat/messages/`

Active model areas:

- `authx`: `Department`, `Role`, `UserProfile`
- `loggingx`: `ApiRequestLog`, `LoginEventLog`, `ServiceLog`, `ChatLog`
- `chat`: `ChatSession`, `ChatMessage`

Future app shells remain:

- `knowledge`
- `rag`
- `graph`
- `evaluation`
- `adminx`

Views should stay thin. Domain logic should live in service modules, graph logic in `graph`, and retrieval/prompt/citation helpers in `rag`.
