# SKILLS.md

This file lists project-specific skills that a coding agent should apply when building the Doctor Chat platform.

These are not installed Codex skills. They are repository-local working agreements and checklists.

## Skill: Rubicon Pattern Translation

Use when adapting a Rubicon mechanism into Doctor Chat.

Steps:
1. Identify the Rubicon pattern, not just the file.
2. Decide whether the pattern is still useful in a medical chatbot.
3. Strip product/Samsung/cloud-specific assumptions.
4. Rebuild the pattern with Doctor Chat naming and medical safety constraints.
5. Add tests around the adapted behavior.

Good candidates:
- standard API envelope
- login/API/chat/module logs
- prompt registry
- admin-managed prompt templates
- background indexing/evaluation jobs
- debug traces by pipeline section
- appraisal/evaluation flows

Do not blindly copy:
- hardcoded paths like `/www/alpha`
- cloud-only Azure AI Search assumptions
- Samsung product prompts
- hardcoded secrets
- direct `django.setup()` in import-time modules

## Skill: LangGraph Workflow Design

Use when changing chatbot flow.

Checklist:
- Define typed state before writing nodes.
- Keep each node small and named by behavior.
- Node input is state; node output is a partial state update.
- Use conditional edges for invalid input, red flags, no-doc state, low confidence, and normal RAG.
- Persist graph path and node timing.
- Write unit tests for branch decisions.
- Do not hide important side effects inside prompt functions.

Recommended baseline nodes:
- `validate_input`
- `normalize_query`
- `classify_medical_intent`
- `detect_red_flags`
- `decide_rag_route`
- `retrieve_documents`
- `rerank_documents`
- `synthesize_answer`
- `safety_review`
- `format_response`
- `persist_logs`

## Skill: Medical RAG Safety

Use when adding prompts, retrieval, answer generation, or UI text.

Rules:
- Use RAG citations for medical claims.
- Do not invent sources.
- Do not provide definitive diagnosis as the system's own authority.
- Handle emergencies and red flags with escalation.
- State uncertainty clearly.
- If retrieved evidence is weak or missing, say so.
- Separate patient-facing wording from clinician-facing decision support.
- Synthetic data only in tests.

Safety test examples:
- chest pain + shortness of breath routes to urgent escalation
- stroke-like symptoms route to urgent escalation
- medication dose request without source refuses or asks for approved source
- no indexed docs returns a no-knowledge response
- retrieved docs are cited in final answer

## Skill: Local Open-Source Infrastructure

Use when adding infrastructure, search, embedding, or model runtime.

Preferred services:
- PostgreSQL for relational data
- pgvector for MVP vector retrieval in Supabase/Postgres
- dedicated vector stores only as future optional adapters if corpus scale, hybrid retrieval, or independent vector scaling requires them
- Redis for cache and jobs
- MinIO for document storage
- sentence-transformers FastAPI service for embeddings and reranking
- Ollama for MVP local LLM runtime
- vLLM as an optional OpenAI-compatible runtime

Rules:
- Everything must run through Docker Compose for local development.
- New environment variables need `.env.example`.
- Avoid cloud-only services in the required path.
- Keep provider adapters behind interfaces.
- Model names and service URLs must be configurable.

## Skill: Prompt Registry And Versioning

Use when adding or changing prompts.

Checklist:
- Store prompt templates in code or DB with a stable key.
- Track prompt version in chat logs.
- Keep medical safety instructions near answer-generation prompts.
- Adapt Rubicon prompt structures, not product wording.
- Add snapshot tests for critical prompts.
- Record prompt key/version in graph run metadata.

Prompt categories:
- query rewrite
- language detection
- medical intent classification
- red-flag detection
- retrieval routing
- answer synthesis
- safety review
- response formatting
- related question generation
- session title generation

## Skill: Evidence And Citation Handling

Use when implementing retrieval and answer generation.

Checklist:
- Every retrieved chunk has source ID, title, document ID, page/section if available, and score.
- Reranked chunks preserve source metadata.
- The final answer cites source IDs or compact citation labels.
- Low-score retrieval triggers low-confidence behavior.
- Admin/debug view can inspect retrieved chunks and scores.
- Tests verify citations are present when documents are used.

## Skill: Operational Logging

Use when adding APIs, graph nodes, workers, or admin actions.

Log these fields when available:
- request ID
- user ID
- session ID
- message ID
- graph run ID
- node name
- duration
- status
- error summary
- model name
- prompt version
- retrieved source IDs
- safety flags

Rules:
- Logs must not include raw PHI unless explicitly required and protected by policy.
- Debug views show summaries and metadata, not hidden chain-of-thought.
- Background jobs should write start/end/error records.

## Skill: Vibe Coding Prompt Discipline

Use when asking Codex to implement the project in multiple turns.

Every implementation prompt should include:
- exact goal
- target files/modules
- tests to write
- Docker command to verify
- expected UI/API behavior
- out-of-scope items

Avoid broad prompts like:
- "build the whole chatbot"
- "make it production ready"
- "add RAG"

Prefer prompts like:
- "Implement document upload and indexing status only. Add tests for txt/md upload, chunk creation, and pgvector indexing job enqueue. Do not implement answer generation yet."

## Skill: Verification Before Handoff

Use before claiming a task is complete.

Required:
- Run the relevant test or verification command.
- Read the output.
- Report exact commands run.
- If verification was not possible, say why.

Never say tests pass unless the command was run successfully in the current turn.

## Skill: Automatic Summary Commit And Push

Use after Codex changes repository files.

Checklist:
1. Inspect `git status --short` and separate current-task changes from unrelated dirty files.
2. Run the narrowest relevant verification command plus `git diff --check`.
3. Confirm the current branch is `develop`.
4. Confirm no staged file is `.env`, generated local data, cache output, PHI, or a secret-bearing file.
5. Stage only current-task files.
6. Commit with a small conventional prefix such as `docs:`, `feat:`, `fix:`, `test:`, `refactor:`, or `chore:`.
7. Push `develop` to `origin`.
8. In the final response, include changed-file summary, verification command output summary, commit hash, and push result.

Stop and report instead of committing or pushing when verification fails, branch
is not `develop`, unrelated changes cannot be separated safely, credentials are
missing, push is rejected, or a secret/local data file would be included.

## Skill: Prompt Implementation Log

Use after every user prompt that analyzes or changes the Doctor Chat project.

Append one concise entry to `docs/prompt_implementation_log.md` before the final
handoff. This is the user's running implementation ledger.

Entry checklist:
1. Record the timestamp and branch.
2. Quote or summarize the user's prompt.
3. List code/docs/config files changed in the turn.
4. Summarize what is implemented now.
5. Summarize what works at runtime, for example whether chat can answer,
   whether RAG retrieval is gated by `ready` documents, and whether LLM
   synthesis is active.
6. Summarize known gaps and limitations.
7. Record verification commands and pass/fail results.
8. Record commit/push status when applicable. Report the final commit hash in
   the final response because a commit cannot reliably contain its own final
   hash.

Rules:
- Keep the file append-only.
- Do not include secrets, `.env` values, raw PHI, hidden chain-of-thought,
  generated local data, screenshots, or long logs.
- If no files changed, still append the prompt/status summary unless the user
  explicitly asks not to write project files.
