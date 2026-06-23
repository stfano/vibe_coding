# Prompt Implementation Log

Append-only ledger for user prompts, implementation status, runtime capability,
verification, and git handoff results. Entries must not include secrets, local
`.env` values, raw PHI, hidden chain-of-thought, generated local data,
screenshots, or long logs.

New entries should be written in Korean unless the user explicitly requests
another language. Older entries are preserved as originally written.

## 2026-06-19 - 웹 질문/답변 가능 상태와 다음 단계 프롬프트 정리

- 브랜치: `develop`
- 사용자 요청: "현재 프로젝트 상황이 웹사이트를 통해 질문 답변 가능해? 아니라면 어느 정도 step 이후에 가능한지, 현재 진행상황과 다음 step 프롬프트를 알려줘."
- 이번 턴 변경 파일:
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - 애플리케이션 코드는 변경하지 않았다.
  - 현재 코드와 문서 기준으로 웹 UI 질문/답변 가능 수준, 남은 한계, 다음 구현 step을 정리했다.
- 실행 시점 기준 동작:
  - 프론트엔드에는 `Chat Workspace`가 있고 `/api/chat/messages/`로 질문을 보낸다.
  - 백엔드 chat API는 graph-compatible router를 실행하고, `ready` 문서가 충분히 검색되면 LLM adapter를 호출해 source-grounded answer를 만든다.
  - Supabase에는 HiDoc PD000 sample 100건, KnowledgeDocument 100건, KnowledgeChunk 115건, controlled smoke용 `ready` 문서 1건이 있다.
  - deterministic evaluation은 4개 case가 모두 통과한 상태다.
- 현재 한계:
  - 실제 브라우저 운영 수준으로 안정화하려면 dev server 실행, Ollama runtime/model 준비, 실제 chat smoke test, 에러 UX 개선이 필요하다.
  - full LangGraph runtime, LangChain retriever wiring, prompt registry, streaming chat, graph debug UI, document upload/parsing은 아직 미구현이다.
- 도구 확인:
  - Docker MCP는 `/var/run/docker.sock` 접근 실패로 현재 컨테이너 실행 여부를 확인하지 못했다.
- 검증:
  - 이번 턴은 상태 분석과 문서 로그만 변경했으므로 커밋 전 `git diff --check`를 실행한다.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

## 2026-06-19 - HiDoc PD000 controlled ready-review workflow

- 브랜치: `develop`
- 사용자 요청: "기존 HiDoc pediatric sample에 대해 controlled ready-review workflow를 만들고, Supabase 데이터로 retrieved + LLM synthesis evaluation 경로를 검증해줘. full HiDoc crawling은 실행하지 말아줘."
- 이번 턴 변경 파일:
  - `backend/apps/knowledge/management/commands/prepare_ready_smoke_docs.py`
  - `backend/apps/knowledge/tests/test_prepare_ready_smoke_docs.py`
  - `README.md`
  - `docs/local_dev.md`
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - `prepare_ready_smoke_docs` Django management command를 추가했다.
  - `--dry-run`으로 HiDoc PD000 `needs_review` 후보를 문서 ID, 제목, source URL, external question/answer ID, chunk count, 짧은 preview만 출력한다.
  - 후보 선정은 `disabled` 문서, chunk 없는 문서, citation metadata 없는 chunk 문서를 제외한다.
  - `--mark-ready --document-id ... --confirm`으로 명시한 문서만 `ready`로 승격한다.
  - `--mark-needs-review --document-id ... --confirm`으로 승격 상태를 되돌릴 수 있다.
  - README와 local dev 문서에 dry-run, mark-ready, revert, evaluation 재실행, `total=4 passed=4` 해석을 추가했다.
- 실행 시점 기준 동작:
  - 기존 Review Queue 프론트는 이미 `needs_review`, `ready`, `disabled` 필터와 상태 변경을 보여주므로 UI 변경은 하지 않았다.
  - Supabase 기준 `ExternalQnaRecord`는 `hidoc`/`PD000` 100건이다.
  - Supabase 기준 `KnowledgeDocument`는 `PD000`에서 `ready` 1건, `needs_review` 99건이다.
  - Supabase 기준 `KnowledgeChunk`는 `PD000` 115건이다.
  - 문서 ID 1을 controlled smoke용으로 `ready` 승격했다.
  - `hidoc-pediatric-smoke` dataset은 ready 문서 존재 후 4개 케이스로 seed되며, deterministic evaluation run은 retrieved, low-confidence, no-ready-doc, red-flag 경로를 모두 검증한다.
- Supabase 검증 결과:
  - `prepare_ready_smoke_docs --source hidoc --department-code PD000 --limit 3 --dry-run`: 통과, 후보 3건 출력, 원문 전체 미출력.
  - `prepare_ready_smoke_docs --source hidoc --department-code PD000 --document-id 1 --mark-ready --confirm`: 통과, `changed=1`.
  - `seed_eval_cases --dataset hidoc-pediatric-smoke --source hidoc --department-code PD000`: 통과, `cases=4`, `skipped_ready_cases=0`.
  - `run_chat_eval --dataset hidoc-pediatric-smoke --llm-provider deterministic`: 통과, `run_id=2`, `total=4 passed=4 failed=0 skipped=0`.
  - retrieved case는 citation 1개, retrieved source ID `[1]`, model `llama3.1:8b`, prompt version `source_grounded_answer_v1`을 포함했다.
  - red-flag, no-ready-doc, low-confidence case는 모두 `llm_executed=false`였다.
- 로컬 검증:
  - `pytest apps/knowledge apps/evaluation apps/chat apps/graph apps/rag`: 통과, 55 passed.
  - `ruff check apps/knowledge apps/evaluation apps/chat apps/graph apps/rag`: 통과.
  - `python3 manage.py makemigrations --check --dry-run`: 통과, 변경 없음.
  - 프론트엔드 파일은 변경하지 않아 `npm --prefix frontend run build`는 실행하지 않았다.
- MCP/sub-agent 사용 결과:
  - Postgres MCP query는 SSL self-signed certificate chain 오류로 실패했다.
  - Django ORM을 통해 Supabase 상태를 안전하게 조회했다.
  - sub-agent spawn은 thread limit으로 실패해 로컬 코드 검토로 대체했다.
- 남은 한계:
  - full HiDoc crawling은 실행하지 않았다.
  - 실제 Ollama 기반 LLM smoke는 이번 턴에서 실행하지 않았다. deterministic adapter로 graph/evaluation 경로를 검증했다.
  - full LangGraph runtime, LangChain retriever wiring, prompt registry, streaming chat, document upload/parsing은 아직 다음 단계로 남아 있다.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

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

## 2026-06-22 13:27:37 KST - source-grounded chat runtime 검증 루프 종료

- 브랜치: `develop`
- 사용자 요청: "새 기능을 추가하지 말고 source-grounded chat runtime verification loop를 먼저 닫아줘."
- 이번 턴 변경 파일:
  - `README.md`
  - `apps/README.md`
  - `docs/architecture.md`
  - `docs/medical_safety.md`
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - 애플리케이션 기능 코드는 변경하지 않았다.
  - 현재 dirty worktree를 분리해 Docker/Ollama 기본값 변경, `.dockerignore` 추가, 로컬 Playwright/Codex 산출물을 구분했다.
  - source-grounded chat runtime과 evaluation smoke를 Docker Compose 환경에서 검증했다.
  - 현재 구현과 어긋난 문서 drift만 최소 수정했다.
- 실행 시점 기준 동작:
  - Docker Compose `llm` profile로 backend, frontend, embedding-service, redis, minio, ollama가 실행된다.
  - HiDoc PD000에는 100개 외부 Q&A, 2개 `ready` 문서, 2개 ready chunk가 있다.
  - Ollama `llama3.2:1b` 기반 chat POST가 `source_status=retrieved`, `llm_executed=true`, citations 2개, `model_name=llama3.2:1b`, `prompt_version=source_grounded_answer_v1`를 반환했다.
  - deterministic evaluation run은 4개 케이스 모두 통과했고, red-flag/no-ready/low-confidence fallback은 LLM을 실행하지 않았다.
  - Playwright MCP에서 `http://localhost:5173`의 Backend online, Review Queue, Search Verification, Evaluation Runs, Chat Workspace 표시와 retrieval/search/chat UI 동작을 확인했다.
- 남은 한계:
  - active graph는 아직 실제 LangGraph `StateGraph` 런타임이 아니라 graph-compatible router다.
  - streaming, prompt registry, graph debug UI, document upload/parsing, production auth policy는 아직 미구현이다.
  - host Python pytest는 처음에 `bs4` 미설치로 collection 실패했지만, `/tmp/doctor_llm_pydeps`에 `beautifulsoup4`를 설치한 뒤 동일 범위가 통과했다.
  - `.codex/`, `.playwright-mcp/`, `doctor-chat-ui-verified.png`는 로컬 산출물로 커밋 대상에서 제외해야 한다.
- 검증:
  - `docker compose --profile llm up -d --build`: 통과.
  - `docker compose ps`: backend, frontend, embedding-service, redis, minio, ollama 실행 확인.
  - `curl -fsS http://127.0.0.1:8000/api/health/`: 통과.
  - `curl -fsS http://127.0.0.1:5173/`: 통과.
  - `docker compose exec ollama ollama list`: `llama3.2:1b`, `llama3.1:8b` 확인.
  - `docker compose exec backend pytest apps/evaluation apps/chat apps/graph apps/rag apps/knowledge`: 통과, 55 passed.
  - `PYTHONPATH=/tmp/doctor_llm_pydeps pytest apps/evaluation apps/chat apps/graph apps/rag apps/knowledge`: 통과, 55 passed.
  - `ruff check apps/evaluation apps/chat apps/graph apps/rag apps/knowledge`: 통과.
  - `npm --prefix frontend run build`: 통과.
  - `docker compose exec backend python manage.py seed_eval_cases --dataset hidoc-pediatric-smoke --source hidoc --department-code PD000`: 통과, 4 cases.
  - `docker compose exec backend python manage.py run_chat_eval --dataset hidoc-pediatric-smoke --llm-provider deterministic`: 통과, total=4 passed=4 failed=0 skipped=0.
  - source-grounded chat API smoke: 통과, retrieved/LLM/citation/model/prompt metadata 확인.
  - Playwright MCP browser smoke: 통과, 운영 패널과 search/chat UI 확인.
  - `docker compose config --quiet`: 통과.
  - `git diff --check`: 통과.
- 커밋/푸시:
  - unrelated/local dirty files가 함께 존재하므로 자동 커밋/푸시는 보류한다.

## 2026-06-22 13:03:56 KST - 다음 단계 분석 및 실행 프롬프트 작성

- 브랜치: `develop`
- 사용자 요청: "지금 나의 프로젝트 상황에서 다음 step이 뭔지 알려주고 그에 맞는 프롬프트 작성해서 알려줘 mcp, subagent, skill 적극 활용해서"
- 이번 턴 변경 파일:
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - 애플리케이션 코드는 변경하지 않았다.
  - `superpowers` skills와 병렬 subagent를 사용해 백엔드/RAG, 프론트 운영 UI, 테스트/문서/최근 상태를 분리 분석했다.
  - 다음 단계는 새 기능 추가보다 현재 dirty worktree와 미완료 runtime smoke 검증을 먼저 닫는 것으로 판단했다.
- 실행 시점 기준 동작:
  - 채팅은 ready 문서 검색, citation, source-grounded LLM 합성, red-flag/no-ready/low-confidence 분기를 지원한다.
  - evaluation workbench와 review/search verification UI가 존재한다.
  - 실제 LangGraph `StateGraph` 런타임, streaming, prompt registry, graph debug UI, document upload pipeline은 아직 다음 단계로 남아 있다.
- 남은 한계:
  - 현재 작업 트리에 이전 변경 및 로컬 산출물이 섞여 있어 이 분석 턴의 로그 변경만 안전하게 커밋하기 어렵다.
  - 이 턴에서는 Docker/Ollama/browser smoke를 직접 재실행하지 않았다.
- 검증:
  - `git diff --check` 실행 예정.
- 커밋/푸시:
  - unrelated dirty worktree 때문에 이 턴에서 커밋/푸시는 중단하고 최종 응답에서 사유를 보고한다.

## 2026-06-19 - WSL Docker Compose 빌드 안정화 및 Ollama 로컬 스모크 기본값 조정

- 브랜치: `develop`
- 사용자 요청: "`docker compose up --build`에서 `failed to fetch metadata: signal: bus error`가 나는데 WSL Docker/Ollama/Playwright까지 직접 실행해 질문 답변이 되는지 테스트하고 오류 없이 동작되도록 수정해줘."
- 이번 턴 변경 파일:
  - `backend/.dockerignore`
  - `frontend/.dockerignore`
  - `embedding-service/.dockerignore`
  - `docker-compose.yml`
  - `.env.example`
  - `backend/config/settings.py`
  - `backend/apps/rag/llms.py`
  - `README.md`
  - `docs/local_dev.md`
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - Docker build context에 캐시, 가상환경, node_modules, 로그 파일이 들어가지 않도록 서비스별 `.dockerignore`를 추가했다.
  - Docker Desktop 잔여 user-local CLI/plugin 충돌을 정리하고 WSL Docker CLI/Compose/Buildx 경로가 정상 동작하는지 확인했다.
  - `docker compose up -d --build`가 backend, frontend, embedding-service를 끝까지 빌드하고 재기동하는 것을 확인했다.
  - Ollama 컨테이너를 실행하고 `llama3.1:8b` 모델 pull까지 완료했다.
  - WSL CPU 환경에서 `llama3.1:8b` 첫 로딩이 180초 안에도 완료되지 않아 chat API가 timeout 500을 반환하는 것을 로그로 확인했다.
  - 로컬 스모크 테스트 기본 모델을 더 가벼운 `llama3.2:1b`로 변경하고 timeout 기본값을 `180`초로 올렸다. 8B 모델은 `CHAT_LLM_MODEL=llama3.1:8b`로 명시하면 계속 사용할 수 있다.
- 실행 시점 기준 동작:
  - `docker compose up -d --build` 경로의 Buildx metadata bus error는 재현되지 않는다.
  - `http://localhost:5173` 프론트는 Playwright MCP에서 열렸고 Backend online, Review Queue, Evaluation Runs가 표시됐다.
  - `http://127.0.0.1:5173`로 열면 프론트 설정이 `localhost:8000`을 호출하므로 CORS mismatch가 발생한다. 정상 테스트 URL은 `http://localhost:5173`이다.
  - 실제 LLM 질문 답변 검증은 backend 컨테이너에 `llama3.2:1b` 기본값을 재적용한 뒤 재실행해야 한다.
- 남은 한계:
  - Docker backend 재생성 명령이 자동 승인 리뷰의 usage limit로 거절되어, `llama3.2:1b` 적용 후 최종 chat API/UI 질문 검증은 이 턴에서 완료하지 못했다.
  - WSL 환경에는 `/usr/local/lib/docker/cli-plugins` 아래 Docker Desktop 잔여 root-owned symlink 경고가 남아 있을 수 있다. 완전 제거는 사용자가 sudo로 수행해야 한다.
- 검증:
  - `docker compose up -d --build`: 통과, backend/frontend/embedding-service 빌드 및 재기동 확인.
  - `curl -fsS http://127.0.0.1:8000/api/health/`: 통과.
  - `curl -fsS http://127.0.0.1:5173/`: 통과.
  - Playwright MCP `http://localhost:5173/`: Backend online 및 운영 패널 표시 확인.
  - `ollama pull llama3.1:8b`: 통과.
  - `ollama pull llama3.2:1b`: 통과.
  - `PYTHONPATH=/tmp/doctor_llm_pydeps pytest apps/rag/tests/test_llm_adapters.py`: 통과, 3 passed.
  - `git diff --check`: 통과.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

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

## 2026-06-22 13:33:30 KST - 로컬 실행 방법 및 UI 기능 안내

- 브랜치: `develop`
- 사용자 요청: "현 프로젝트 구현된 것을 직접 테스트해보려고 하는데, 로컬 실행 방법과 실행 시 각 UI 기능을 알려줘."
- 이번 턴 변경 파일:
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - 애플리케이션 코드는 변경하지 않았다.
  - 현재 문서와 프론트엔드 컴포넌트를 기준으로 로컬 Docker 실행 절차, 선택적 Ollama 실행, 주요 URL, UI 패널별 기능을 정리했다.
- 실행 시점 기준 동작:
  - Docker Compose로 backend, frontend, embedding-service, redis, minio를 실행할 수 있고 `llm` profile로 Ollama를 추가 실행할 수 있다.
  - frontend는 Backend Health, Local Services, Review Queue, Search Verification, Evaluation Runs, Chat Workspace 패널을 제공한다.
  - chat은 ready 문서 검색 성공 시 source-grounded LLM 답변을 표시하고, fallback/red-flag 경로에서는 LLM 실행을 억제한다.
- 남은 한계:
  - full LangGraph `StateGraph`, streaming chat, prompt registry, graph debug UI, document upload/parsing, production auth policy는 아직 미구현이다.
  - Review Queue와 Search Verification은 현재 HiDoc PD000 샘플 중심으로 고정되어 있다.
- 검증:
  - 문서/코드 읽기 중심 안내 작업이며 애플리케이션 검증 명령은 실행하지 않았다.
  - 커밋 전 `git diff --check`를 실행한다.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

## 2026-06-22 15:52:38 KST - 다음 구현 단계 및 프롬프트 제안

- 브랜치: `develop`
- 사용자 요청: "다음 step으로 진행해야 할 작업 및 프롬프트 알려줘."
- 이번 턴 변경 파일:
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - 애플리케이션 코드는 변경하지 않았다.
  - 현재 검색 검증이 deterministic token-hash embedding과 cosine/pgvector 기반으로 동작한다는 점을 전제로 다음 구현 단계를 정리했다.
  - 다음 step으로 실제 semantic embedding/reranker 기반 검색 품질 개선과 검색 검증 UI의 투명성 보강을 제안했다.
- 실행 시점 기준 동작:
  - Supabase Postgres의 HiDoc PD000 ready chunk를 대상으로 검색과 source-grounded chat이 동작한다.
  - Search Verification은 query rewrite, NER, reranking 없이 raw query embedding 검색만 수행한다.
- 남은 한계:
  - 실제 sentence-transformers embedding/reranker, query rewrite, NER, LangChain retriever, full LangGraph runtime은 아직 미구현이다.
  - 현재 추천 프롬프트는 embedding/reranker와 검색 검증 강화에 초점을 둔다.
- 검증:
  - 문서/분석 로그 변경만 있으므로 `git diff --check`를 실행한다.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

## 2026-06-22 16:27:17 KST - semantic embedding 기반 검색 품질 vertical slice

- 브랜치: `develop`
- 사용자 요청: "다음 vertical slice로 검색 품질을 개선하고 deterministic token-hash embedding 검색을 실제 semantic embedding 기반 검색으로 전환해줘."
- 이번 턴 변경 파일:
  - `.env.example`
  - `README.md`
  - `backend/apps/knowledge/services.py`
  - `backend/apps/knowledge/tests/test_review_api.py`
  - `backend/apps/rag/embeddings.py`
  - `backend/apps/rag/retrieval.py`
  - `backend/apps/rag/tests/test_embeddings_and_retrieval.py`
  - `docker-compose.yml`
  - `docs/architecture.md`
  - `docs/local_dev.md`
  - `embedding-service/Dockerfile`
  - `embedding-service/app/__init__.py`
  - `embedding-service/app/main.py`
  - `embedding-service/requirements.txt`
  - `embedding-service/requirements-semantic.txt`
  - `embedding-service/tests/test_main.py`
  - `frontend/src/SearchVerificationPanel.tsx`
  - `frontend/src/api.ts`
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - embedding-service에 sentence-transformers 기반 `/embed` 경로와 deterministic fallback을 추가했다.
  - embedding-service에 `/rerank` API contract와 deterministic rerank fallback을 추가했다.
  - Docker 빌드에서 semantic dependency를 선택 설치하며 CPU-only torch wheel을 사용하도록 고정했다.
  - backend `HttpEmbeddingAdapter`가 `/embed` 응답의 provider, model, dimensions, fallback metadata를 기록하도록 했다.
  - Search Verification API가 `llm_executed=false`, `graph_executed=false`를 유지하면서 retrieval metadata, raw score, optional rerank score를 반환하도록 했다.
  - Search Verification UI가 embedding provider/model/dimensions, vector metric, rerank 상태, score/raw score를 표시하도록 했다.
- 실행 시점 기준 동작:
  - Docker Compose health 기준 embedding-service는 `EMBEDDING_BACKEND=sentence-transformers`, backend는 embedding service configured 상태로 기동된다.
  - 현재 로컬 Compose DB는 SQLite fallback으로 동작해 Search Verification runtime smoke는 sqlite 전용 deterministic adapter를 사용했다.
  - 현재 DB에는 HiDoc PD000 기준 ready 문서 15건, needs_review 문서 69건, disabled 문서 16건, chunk 115건이 있었다.
  - Search Verification API smoke는 ready-only 검색 결과와 score/raw score/retrieval metadata를 반환했고, red-flag query는 retrieval을 suppress했다.
  - Playwright MCP에서 `http://localhost:5173` Search Verification 결과에 provider/model/dimensions, metric, score/raw score가 표시됨을 확인했다.
- 남은 한계:
  - query rewriting, NER, full LangGraph StateGraph 리팩터링, streaming chat, prompt registry, document upload, auth policy, graph debug UI는 구현하지 않았다.
  - `/rerank`는 API contract와 deterministic fallback 중심이며 실제 CrossEncoder 모델은 optional 설정이다.
  - 로컬 SQLite verification smoke는 HTTP semantic provider가 아니라 deterministic adapter를 사용한다. Supabase/Postgres 경로에서는 `EMBEDDING_PROVIDER=http`와 embedding-service를 통해 semantic embedding provider를 사용한다.
  - `mykor/KURE-v1` 최초 모델 로딩은 로컬 네트워크/캐시 상태에 따라 오래 걸릴 수 있어 직접 semantic 모델 로딩 smoke는 완료하지 않았다.
- 검증:
  - `pytest tests/test_main.py -q` in `embedding-service`: 통과, 2 passed.
  - `PYTHONPATH=/tmp/doctor_llm_pydeps pytest apps/rag/tests/test_embeddings_and_retrieval.py apps/knowledge/tests/test_review_api.py -q`: 통과, 15 passed.
  - `docker compose --profile llm up -d --build`: 통과. 최초 CUDA 포함 torch 설치 시도는 중단하고 CPU-only torch requirements로 수정 후 재실행했다.
  - `docker compose exec backend python manage.py migrate`: 통과, no migrations to apply.
  - `docker compose exec -e CHAT_LLM_PROVIDER=deterministic backend pytest apps/rag apps/knowledge apps/graph apps/chat`: 통과, 49 passed.
  - `npm --prefix frontend run build`: 통과.
  - `curl -fsSL http://127.0.0.1:8080/health`: 통과.
  - `curl -fsSL http://127.0.0.1:8000/api/health/`: 통과.
  - Search Verification API smoke: 통과, `llm_executed=false`, `graph_executed=false`, retrieval metadata와 score 반환 확인.
  - red-flag Search Verification API smoke: 통과, `source_status=retrieval_suppressed`, retrieval `not_executed` 확인.
  - Playwright MCP browser smoke for `http://localhost:5173`: 통과.
  - `git diff --check`: 통과.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

## 2026-06-22 18:44:36 KST - Supabase/pgvector semantic retrieval verification loop

- 브랜치: `develop`
- 사용자 요청: "Supabase/Postgres + pgvector + `EMBEDDING_PROVIDER=http` + embedding-service 조합에서 실제 semantic 검색 경로를 검증하고, 필요한 최소 문서 drift만 수정해줘."
- 이번 턴 변경 파일:
  - `.env.example`
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - `.env.example`의 `EMBEDDING_PROVIDER` 기본값을 현재 Compose/문서 의도와 맞게 `http`로 수정했다.
  - 로컬 `.env` 값은 수정하거나 커밋하지 않았다.
  - 전체 HiDoc crawl 없이 기존 HiDoc PD000 데이터 중 관련 ExternalQnaRecord 6, 7, 8과 evaluation 기준 ExternalQnaRecord 1만 HTTP semantic embedding으로 재색인했다.
  - `prepare_ready_smoke_docs --dry-run`으로 후보를 확인한 뒤 document 6만 `ready`로 승격했다.
- 실행 시점 기준 동작:
  - backend는 PostgreSQL을 사용 중이며 pgvector extension이 활성화되어 있다.
  - embedding-service `/embed`는 `provider=sentence-transformers`, `model=mykor/KURE-v1`, `fallback_used=false`로 응답했다.
  - Search Verification API는 Supabase/pgvector + HTTP embedding-service 경로에서 `embedding_transport=http`, `embedding_provider=sentence-transformers`, `embedding_dimensions=1024`, `embedding_fallback_used=false`를 반환했다.
  - ready-only normal query `아기 고환 물집 아기띠`는 document 6을 rank 1, score 약 0.709로 반환했다.
  - red-flag query `소아 호흡곤란 청색증 응급`은 retrieval을 suppress하고 `llm_executed=false`, `graph_executed=false`를 유지했다.
  - deterministic evaluation smoke는 재색인 전 2/4 실패했으나, dataset 기준 ready 문서 1을 semantic 재색인한 뒤 4/4 통과했다.
  - Playwright MCP에서 `http://localhost:5173` Search Verification UI가 semantic provider/model/dimensions, score/raw score, red-flag suppression을 표시함을 확인했다.
- 남은 한계:
  - 전체 PD000 corpus를 재색인하지 않았으므로 아직 deterministic-era vector가 섞여 있을 수 있다.
  - `/rerank`는 여전히 기본 deterministic contract 중심이며 실제 CrossEncoder rerank 경로는 검증하지 않았다.
  - full LangGraph StateGraph, streaming, prompt registry, document upload, auth policy, graph debug UI, query rewriting, NER는 구현하지 않았다.
  - Playwright 콘솔에 favicon 404가 있었으나 Search Verification 동작에는 영향이 없었다.
- 검증:
  - `git status --short --branch`: `develop`, 기존 미추적 로컬 산출물과 이번 `.env.example` 변경 확인.
  - `docker compose ps`: backend, frontend, embedding-service, redis, minio 실행 확인.
  - `curl -fsSL http://127.0.0.1:8080/health`: 통과.
  - embedding-service `/embed` fallback 허용 모드: `sentence-transformers`, fallback false 확인.
  - embedding-service fallback 불허 모드: `sentence-transformers`, fallback false 확인.
  - backend DB 상태 출력: PostgreSQL vendor, pgvector extension 활성화, PD000 row/status/model/dimension 분포 확인.
  - `docker compose exec backend python manage.py migrate`: 통과, no migrations to apply.
  - `docker compose exec -e CHAT_LLM_PROVIDER=deterministic backend pytest apps/rag apps/knowledge apps/graph apps/chat apps/evaluation`: 통과, 56 passed.
  - `pytest tests/test_main.py -q` in `embedding-service`: 통과, 2 passed.
  - `npm --prefix frontend run build`: 통과.
  - Search Verification API smoke normal/red-flag: 통과.
  - `docker compose exec backend python manage.py seed_eval_cases --dataset hidoc-pediatric-smoke --source hidoc --department-code PD000`: 통과.
  - `docker compose exec backend python manage.py run_chat_eval --dataset hidoc-pediatric-smoke --llm-provider deterministic`: 최종 통과, 4 passed / 0 failed / 0 skipped.
  - Playwright MCP smoke: 통과.
  - `git diff --check`: 통과.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

## 2026-06-23 09:23:58 KST - 다음 LangGraph 구현 프롬프트 작성

- 브랜치: `develop`
- 사용자 요청: "지금 프로젝트 다음 step 프롬프트 작성해서 알려줘 mcp, sub agent, skill 적극 활용해주고 최신 프롬프트 기술도 사용해줘"
- 이번 턴 변경 파일:
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - 필수 문서와 현재 코드 상태를 검토해 다음 구현 slice를 정리했다.
  - Context7 MCP로 LangGraph `StateGraph` 최신 사용 방식을 확인했다.
  - OpenAI 공식 prompt/structured output 문서를 확인해 프롬프트 구성에 명확한 목표, 범위, 출력 계약, 검증 명령, out-of-scope, self-review 지시를 반영했다.
  - RAG/LangGraph 서브 에이전트와 frontend/ops UI 서브 에이전트를 병렬로 사용해 다음 backend slice와 후속 UI slice를 비교했다.
- 실행 시점 기준 동작:
  - 현재 chat path는 review-gated retrieval, semantic embedding metadata, source-grounded answer synthesis, deterministic evaluation smoke를 갖추고 있다.
  - 핵심 남은 backend gap은 수동 `_run_node()` 기반 graph-compatible router를 실제 LangGraph `StateGraph` 런타임으로 전환하는 것이다.
- 남은 한계:
  - 이번 턴은 다음 구현 프롬프트 작성만 수행했고 코드 구현은 하지 않았다.
  - UI operational trace/evaluation triage workbench는 LangGraph 전환 이후 후속 slice로 남겼다.
- 검증:
  - `git status --short --branch`: 통과, 기존 미추적 로컬 산출물과 이번 문서 변경 확인.
  - `git diff --check`: 통과.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.

## 2026-06-23 10:18:26 KST - LangGraph StateGraph chat workflow 전환

- 브랜치: `develop`
- 사용자 요청: "manual chat safety/RAG router를 실제 LangGraph StateGraph runtime으로 교체하고 기존 run_chat_safety_graph 계약과 chat/evaluation 응답 shape를 유지해줘."
- 이번 턴 변경 파일:
  - `backend/apps/graph/state.py`
  - `backend/apps/graph/nodes.py`
  - `backend/apps/graph/workflow.py`
  - `backend/apps/graph/router.py`
  - `backend/apps/graph/tests/test_chat_safety_router.py`
  - `backend/apps/evaluation/services.py`
  - `backend/apps/chat/tests/test_chat_api.py`
  - `backend/apps/evaluation/tests/test_evaluation_workbench.py`
  - `docs/architecture.md`
  - `docs/prompt_implementation_log.md`
- 현재 구현 내용:
  - `run_chat_safety_graph()` public entrypoint는 유지하면서 내부 실행을 LangGraph `StateGraph` workflow로 전환했다.
  - typed graph state, small node functions, workflow builder를 `apps.graph` 하위 모듈로 분리했다.
  - graph metadata에 `runtime=langgraph_stategraph`, graph path, node summaries, model/prompt metadata, retrieved source IDs, sanitized error summary를 포함한다.
  - retrieval/LLM node 실패를 raw exception 전파 대신 `source_status=graph_error` 안전 fallback으로 변환한다.
  - red-flag, no-ready, low-confidence branch는 LLM을 호출하지 않고, retrieved branch만 LLM을 호출하도록 테스트로 고정했다.
  - ready 문서가 여러 건일 때 evaluation smoke dataset이 실제 retrieval 가능한 ready 문서를 선택하도록 seed 로직을 보강했다.
- 실행 시점 기준 동작:
  - chat API와 evaluation 서비스는 기존 응답 shape를 유지하면서 새 LangGraph runtime metadata를 저장한다.
  - ready-only retrieval gate, citation metadata, low-confidence gate, red-flag urgent escalation, deterministic evaluation path가 유지된다.
- 남은 한계:
  - streaming/SSE, frontend graph debug UI, prompt registry, document upload/parsing, query rewrite/NER, real reranker integration은 이번 범위가 아니다.
  - graph node error summary는 node 이름 단위의 sanitize된 요약만 제공하며 provider별 상세 진단은 아직 별도 operational log로 확장하지 않았다.
- 검증:
  - `env PYTHONDONTWRITEBYTECODE=1 CHAT_LLM_PROVIDER=deterministic pytest apps/graph/tests/test_chat_safety_router.py -q -p no:cacheprovider`: 통과, 7 passed.
  - `env PYTHONDONTWRITEBYTECODE=1 CHAT_LLM_PROVIDER=deterministic pytest apps/graph apps/chat apps/evaluation apps/rag -q -p no:cacheprovider`: 통과, 31 passed.
  - `env PYTHONDONTWRITEBYTECODE=1 CHAT_LLM_PROVIDER=deterministic python manage.py seed_eval_cases --dataset hidoc-pediatric-smoke --source hidoc --department-code PD000`: 실패, 현재 shell에 `python` 실행 파일이 없어 `python3`로 재실행했다.
  - `env PYTHONDONTWRITEBYTECODE=1 CHAT_LLM_PROVIDER=deterministic python3 manage.py seed_eval_cases --dataset hidoc-pediatric-smoke --source hidoc --department-code PD000`: 통과.
  - `env PYTHONDONTWRITEBYTECODE=1 CHAT_LLM_PROVIDER=deterministic python3 manage.py run_chat_eval --dataset hidoc-pediatric-smoke --llm-provider deterministic`: 최초 실행은 기존 evaluation seed drift로 2/4 실패했고, seed 로직 보강 후 최종 통과, 4 passed / 0 failed / 0 skipped.
  - `git diff --check`: 통과.
- 커밋/푸시:
  - 최종 커밋 해시와 push 결과는 최종 응답에서 보고한다.
