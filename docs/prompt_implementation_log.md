# Prompt Implementation Log

Append-only ledger for user prompts, implementation status, runtime capability,
verification, and git handoff results. Entries must not include secrets, local
`.env` values, raw PHI, hidden chain-of-thought, generated local data,
screenshots, or long logs.

## 2026-06-18 - Automatic per-prompt implementation ledger

- Branch: `develop`
- User prompt: "매 프롬프트마다 코드가 어디 수정됐는지, 어디까지 구현됐는지, 실행시에 어디까지 구현되어있는건지 ... 별도 .md 파일 생성해서 ... 계속 쌓이게 정리해줘 ... 그리고 지금 어디까지 구현됐는지도 알려줘"
- Files changed in this turn:
  - `AGENTS.md`
  - `SKILLS.md`
  - `docs/prompt_implementation_log.md`
- Implemented now:
  - Added a standing agent instruction requiring Codex to append a concise prompt/status entry after each project prompt.
  - Added a repo-local `Prompt Implementation Log` skill/checklist to `SKILLS.md`.
  - Created this append-only project ledger.
- Current runtime implementation status:
  - Frontend: React/Vite operational workspace exists with backend health, service status, review queue, search verification, and chat panels.
  - Backend: Django/DRF APIs exist for health, chat, knowledge document review, and retrieval verification.
  - Ingestion: HiDoc pediatric sample ingestion exists and previously loaded 100 `ExternalQnaRecord` rows; full crawl command exists but should be run intentionally, not automatically.
  - Indexing/RAG: External Q&A records can be converted to `KnowledgeDocument` and `KnowledgeChunk`; retrieval uses pgvector/Postgres when available and defaults to `ready` documents only.
  - Chat: chat API runs the graph-compatible router. Red-flag, no-ready-document, and low-confidence branches return fallback responses without LLM execution.
  - Answer generation: when ready chunks are retrieved with sufficient confidence, chat can call a local LLM adapter and return a source-grounded answer with citations, `llm_executed`, model name, prompt version, graph path, and retrieved source IDs.
  - LLM runtime: Ollama-compatible adapter and deterministic test adapter exist. Ollama must be running and the configured model must be pulled for real local generation.
- Known gaps and limitations:
  - Full LangGraph runtime integration is not implemented yet; current graph is graph-compatible service code.
  - LangChain retrievers/prompt templates are not wired into chat yet.
  - Document upload/parsing, prompt registry, evaluation/golden-set workflow, streaming chat, graph debug trace UI, production auth policy, production reranking, and full HiDoc crawl are not implemented.
  - HiDoc records remain candidate content unless reviewed and source-use permissions are handled.
  - Chat will not use `needs_review` documents; at least one document must be marked `ready` for RAG answer synthesis.
- Verification for this turn:
  - `git diff --check`: passed.
  - `git branch --show-current`: `develop`.
  - No backend/frontend test run was needed because this turn changed only project workflow documentation.
- Commit/push:
  - Pending before final handoff; final commit hash and push result are reported in the assistant response.
