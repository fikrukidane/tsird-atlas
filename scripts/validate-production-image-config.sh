#!/usr/bin/env bash
# Read-only guard: production Compose must reference prebuilt images and must
# not include local build directives for application-serving services.
set -euo pipefail

APP_ROOT="${TSIRD_APP_ROOT:-.}"
cd "$APP_ROOT"

for variable in TSIRD_WEB_IMAGE TSIRD_API_IMAGE TSIRD_EDGE_IMAGE; do
  value="${!variable:-}"
  [[ -n "$value" ]] || { echo "FAIL: $variable is required for production" >&2; exit 1; }
  [[ "$value" != *REPLACE_ME* ]] || { echo "FAIL: $variable still has a placeholder tag" >&2; exit 1; }
done

rendered="$(docker compose -f docker-compose.yml -f docker-compose.production.yml config)"
for service in tsird-web tsird-api tsird-edge; do
  service_block="$(awk -v target="  ${service}:" '
    $0 == target { collect=1 }
    collect { print }
    collect && /^  [a-z0-9-]+:$/ && $0 != target { exit }
  ' <<<"$rendered")"
  grep -Fq 'image:' <<<"$service_block" || { echo "FAIL: $service has no production image" >&2; exit 1; }
  if grep -Fq 'build:' <<<"$service_block"; then
    echo "FAIL: $service still has a build directive" >&2
    exit 1
  fi
done

if grep -Fq '  tsird-etl:' <<<"$rendered"; then
  echo 'FAIL: tsird-etl is present in the production default configuration' >&2
  exit 1
fi

echo 'PASS: production Compose requires prebuilt web/API/edge images and excludes ETL from the default profile.'
