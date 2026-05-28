# Doctor Chat Sub-Agents

This directory contains project-local Codex sub-agent definitions in TOML.

Use these agents as role prompts or routing hints when work naturally falls into a focused slice. They do not replace `AGENTS.md`; every agent must still follow the repository-wide instructions, medical safety rules, and verification expectations.

Recommended initial set:

- `backend-django-agent`
- `medical-safety-agent`
- `rag-langgraph-agent`
- `knowledge-indexing-agent`
- `frontend-ops-ui-agent`
- `infra-local-dev-agent`
- `test-verification-agent`
- `security-secrets-agent`
- `git-release-agent`

Keep agent scopes narrow. Add a new agent only when a recurring task needs distinct context, constraints, or verification behavior.
