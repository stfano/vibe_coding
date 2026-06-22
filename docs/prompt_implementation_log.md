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
