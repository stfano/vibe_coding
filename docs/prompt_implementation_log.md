# Prompt Implementation Log

Append-only ledger for user prompts, implementation status, runtime capability,
verification, and git handoff results. Entries must not include secrets, local
`.env` values, raw PHI, hidden chain-of-thought, generated local data,
screenshots, or long logs.

New entries should be written in Korean unless the user explicitly requests
another language. Older entries are preserved as originally written.

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

## 2026-06-19 - 프롬프트 구현 로그 한국어 작성 규칙

- 브랜치: `develop`
- 사용자 요청: "`docs/prompt_implementation_log.md`에 정리할 때 한국어로 정리되게 해줘"
- 이번 턴 변경 파일:
  - `AGENTS.md`
  - `SKILLS.md`
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - 앞으로 `docs/prompt_implementation_log.md`에 추가되는 새 항목은 사용자가 다른 언어를 명시하지 않는 한 한국어로 작성하도록 지침을 추가했다.
  - 기존 로그 항목은 append-only 원칙에 따라 그대로 보존한다.
- 실행 시점 기준 동작:
  - 애플리케이션 런타임 코드는 변경하지 않았다.
  - 이후 Codex 작업 정리 로그는 한국어 항목으로 누적된다.
- 남은 한계:
  - 이전에 영어로 작성된 항목은 기록 보존 원칙상 자동 번역하지 않았다.
- 검증:
  - 커밋 전 `git diff --check` 실행 예정.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

## 2026-06-18 - Next-step implementation prompt

- Branch: `develop`
- User prompt: "현 프로젝트에서 다음 step 으로 뭘 해야 할지 프롬프트 작성해줘 자세하고, 세밀하게 llm이 잘 수행되도록 프롬프트 작성해줘. skills, mcp, shub agent 적극 활용해줘"
- Files changed in this turn:
  - `docs/prompt_implementation_log.md`
- Implemented now:
  - No application code changed.
  - Added this ledger entry for the prompt-design turn.
- Current runtime implementation status:
  - Chat can generate source-grounded answers only when `ready` chunks are retrieved with sufficient confidence and a local LLM runtime is available.
  - RAG retrieval is review-gated; `needs_review` documents are excluded from chat.
  - The project lacks an evaluation/golden-set workflow to repeatedly test retrieval quality, source-grounded answer behavior, citation coverage, fallback branches, and regression risk.
- Recommended next step:
  - Build a narrow evaluation and chat smoke-test workbench before expanding crawling or adding streaming. This gives a repeatable way to prove the current 100-record sample and reviewed ready subset actually produce useful source-grounded answers.
- MCP/sub-agent notes:
  - Sub-agent spawning was unavailable because the agent thread limit was reached.
  - Postgres MCP query was attempted but failed with a self-signed certificate chain error, so the next-step prompt should require local DB status discovery inside the implementation turn.
- Verification for this turn:
  - Pending before final handoff.
- Commit/push:
  - Pending before final handoff; final commit hash and push result are reported in the assistant response.
