#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" && -n "${GITHUB_TOKEN:-}" ]]; then
  export GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_TOKEN"
fi

if [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]]; then
  echo "GITHUB_PERSONAL_ACCESS_TOKEN or GITHUB_TOKEN is required in the environment or .env." >&2
  exit 1
fi

if [[ "$(git rev-parse --abbrev-ref HEAD)" != "develop" ]]; then
  git switch develop
fi

git add -A

if git diff --cached --quiet; then
  echo "No staged changes to commit."
  exit 0
fi

message="${1:-chore: update project state}"
git commit -m "$message"

auth_header="$(
  python3 - <<'PY'
import base64
import os

token = os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"]
print("Authorization: Basic " + base64.b64encode(f"x-access-token:{token}".encode()).decode())
PY
)"

GIT_CONFIG_COUNT=1 \
GIT_CONFIG_KEY_0="http.https://github.com/.extraheader" \
GIT_CONFIG_VALUE_0="$auth_header" \
GIT_TERMINAL_PROMPT=0 \
git push -u origin develop
