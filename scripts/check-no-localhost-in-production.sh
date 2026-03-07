#!/usr/bin/env bash
# check-no-localhost-in-production.sh
#
# Guardrail: fail if any production-served frontend file contains patterns
# that cause browsers to attempt access to localhost / local device services.
#
# Run before every release tag:
#   ./scripts/check-no-localhost-in-production.sh
#
# Exit 0 = clean. Exit 1 = violations found (block the release).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Production-served directories (copied into Docker image by ui/web/Dockerfile)
SCAN_DIRS=(
  "${REPO_ROOT}/ui/web/data"
  "${REPO_ROOT}/ui/web/src"
  "${REPO_ROOT}/ui/web/js"
  "${REPO_ROOT}/ui/web/css"
  "${REPO_ROOT}/ui/web/index.html"
)

# Patterns forbidden in production-served files.
# These cause browsers to attempt local device or localhost access.
FORBIDDEN_PATTERNS=(
  "localhost"
  "127\.0\.0\.1"
  ":18080"
  "registerProtocolHandler"
  "getInstalledRelatedApps"
  "related_applications"
  "web\+"
)

# Files/paths to explicitly exclude from scanning (docs, not served at runtime).
# Add additional exclusions as grep -v patterns if needed.
EXCLUDE_PATTERN="(\.md$|\.txt$|\.bak$|backups/|docs/)"

# ── Run scan ─────────────────────────────────────────────────────────────────

VIOLATIONS=0
VIOLATION_LINES=()

# Build grep pattern (alternation)
GREP_PATTERN=$(IFS='|'; echo "${FORBIDDEN_PATTERNS[*]}")

for target in "${SCAN_DIRS[@]}"; do
  if [[ ! -e "$target" ]]; then
    continue
  fi

  while IFS= read -r line; do
    # Filter out excluded paths
    file=$(echo "$line" | cut -d: -f1)
    if echo "$file" | grep -qE "${EXCLUDE_PATTERN}"; then
      continue
    fi
    VIOLATIONS=$((VIOLATIONS + 1))
    VIOLATION_LINES+=("$line")
  done < <(grep -rn --include="*.js" --include="*.json" --include="*.yaml" \
               --include="*.yml" --include="*.html" \
               -E "${GREP_PATTERN}" "$target" 2>/dev/null || true)
done

# ── Report ───────────────────────────────────────────────────────────────────

if [[ $VIOLATIONS -eq 0 ]]; then
  echo "[OK] Production frontend is clean — no localhost / device-app trigger patterns found."
  exit 0
else
  echo "[FAIL] Found ${VIOLATIONS} forbidden pattern(s) in production-served frontend files:"
  echo ""
  for v in "${VIOLATION_LINES[@]}"; do
    echo "  $v"
  done
  echo ""
  echo "Fix all violations before tagging a release."
  echo "Forbidden patterns: localhost, 127.0.0.1, :18080,"
  echo "  registerProtocolHandler, getInstalledRelatedApps,"
  echo "  related_applications, web+"
  exit 1
fi
