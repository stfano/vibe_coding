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

askpass="$(mktemp)"
trap 'rm -f "$askpass"' EXIT
cat > "$askpass" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  *Username*) printf '%s\n' "x-access-token" ;;
  *Password*) printf '%s\n' "${GITHUB_PERSONAL_ACCESS_TOKEN}" ;;
  *) printf '\n' ;;
esac
EOF
chmod +x "$askpass"

GIT_ASKPASS="$askpass" GIT_TERMINAL_PROMPT=0 git push -u origin develop
