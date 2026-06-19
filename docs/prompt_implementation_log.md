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

## 2026-06-19 - 평가 및 채팅 스모크 테스트 워크벤치 구현

- 브랜치: `develop`
- 사용자 요청: "기존 source-grounded RAG chat을 반복 검증할 evaluation/chat smoke-test workbench를 구현해줘. full HiDoc crawling은 실행하지 말고, golden-set으로 ready retrieval, LLM synthesis, citation metadata, fallback branches를 검증하게 해줘."
- 이번 턴 변경 파일:
  - `backend/apps/evaluation/*`
  - `backend/apps/graph/router.py`
  - `backend/config/urls.py`
  - `frontend/src/api.ts`
  - `frontend/src/App.tsx`
  - `frontend/src/EvaluationPanel.tsx`
  - `frontend/src/styles.css`
  - `README.md`
  - `docs/local_dev.md`
  - `backend/apps/README.md`
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - `EvaluationDataset`, `EvaluationCase`, `EvaluationRun`, `EvaluationResult` 모델과 migration을 추가했다.
  - `seed_eval_cases` 명령으로 HiDoc PD000 smoke dataset을 idempotent하게 생성한다.
  - `run_chat_eval` 명령으로 기존 chat graph를 deterministic/Ollama LLM adapter로 실행하고 결과를 저장한다.
  - evaluation dataset/run/result를 Django Admin과 read-only API에서 확인할 수 있게 했다.
  - 프론트에 `Evaluation Runs` 운영 패널을 추가해 최근 run과 실패 케이스 요약을 볼 수 있게 했다.
  - graph router에는 evaluation용 source/department/low-confidence threshold 옵션을 추가했으며 기본 chat API 동작은 유지했다.
- 실행 시점 기준 동작:
  - ready 문서가 있으면 retrieved/low-confidence/red-flag/no-ready 케이스를 seed하고 deterministic LLM으로 반복 평가할 수 있다.
  - ready 문서가 없으면 retrieved/low-confidence 케이스는 건너뛰고 fallback/red-flag 케이스만 생성한다.
  - red-flag, no-ready-doc, low-confidence 분기는 LLM 미호출 여부를 검증한다.
  - retrieved 케이스는 citation, retrieved source IDs, graph metadata, model name, prompt version을 검증한다.
- 남은 한계:
  - full LangGraph runtime, LangChain retriever wiring, prompt registry, streaming chat, graph debug trace UI는 아직 미구현이다.
  - Supabase에 현재 ready 문서가 없으면 실제 운영 DB smoke run은 2개 fallback 케이스만 실행된다.
  - full HiDoc crawling은 실행하지 않았다.
- 검증:
  - `pytest apps/evaluation apps/chat apps/graph apps/rag apps/knowledge`: 통과.
  - `ruff check apps/evaluation apps/chat apps/graph apps/rag apps/knowledge`: 통과.
  - `python3 manage.py makemigrations --check --dry-run`: 통과.
  - `npm --prefix frontend run build`: 통과.
  - Supabase `python3 manage.py migrate evaluation`: 통과.
  - Supabase `python3 manage.py seed_eval_cases --dataset hidoc-pediatric-smoke --source hidoc --department-code PD000`: 통과, ready 문서 없음으로 2개 케이스 생성 및 2개 ready 케이스 skip.
  - Supabase `python3 manage.py run_chat_eval --dataset hidoc-pediatric-smoke --llm-provider deterministic`: 통과, `total=2 passed=2 failed=0 skipped=0`.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

## 2026-06-19 - 다음 단계 구현 프롬프트 작성

- 브랜치: `develop`
- 사용자 요청: "다음 진행해야할 step 프롬프트 작성해서 알려줘."
- 이번 턴 변경 파일:
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - 애플리케이션 코드는 변경하지 않았다.
  - 현재 프로젝트 상태를 기준으로 다음 구현 단계 프롬프트를 작성했다.
- 실행 시점 기준 동작:
  - evaluation workbench는 구현되어 있고 deterministic fallback/red-flag smoke run은 가능하다.
  - Supabase에는 현재 `ready` 문서가 없어 retrieved/LLM 경로의 실데이터 evaluation은 아직 실행되지 못한다.
- 추천 다음 단계:
  - HiDoc PD000 샘플에서 소수 문서를 검수해 `ready`로 승격하고, deterministic/Ollama 평가를 통해 retrieved 경로, citation, LLM synthesis를 실제 DB 기준으로 검증하는 slice를 진행한다.
- 남은 한계:
  - full crawl, prompt registry, streaming chat, full LangGraph runtime, LangChain retriever wiring은 아직 다음다음 단계로 남긴다.
- 검증:
  - 문서 변경만 있으므로 `git diff --check`를 실행한다.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

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
