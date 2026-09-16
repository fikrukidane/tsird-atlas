#!/usr/bin/env bash
# Read-only, release-time delta check for the constrained TSIRD production host.
# Run from /opt/tigrayinsights/apps/tsird after the normal host inventory has
# already established its baseline. It does not build, pull, start, restart,
# or modify a service.
set -euo pipefail

APP_ROOT="${TSIRD_APP_ROOT:-/opt/tigrayinsights/apps/tsird}"
INGRESS_ROOT="${TSIRD_DROUGHT_INGRESS_ROOT:-/srv/sftp/tsird-release/incoming}"
RELEASE_ROOT="${TSIRD_DROUGHT_RELEASE_ROOT:-${APP_ROOT}/releases/drought}"
MIN_FREE_GIB="${TSIRD_DROUGHT_MIN_FREE_GIB:-2}"
COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.production.yml)

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

require_directory() {
  [[ -d "$1" ]] || fail "required directory is absent: $1"
}

[[ "$MIN_FREE_GIB" =~ ^[0-9]+$ ]] || fail "TSIRD_DROUGHT_MIN_FREE_GIB must be a whole number"
[[ -d "$APP_ROOT" ]] || fail "application root is absent: $APP_ROOT"
cd "$APP_ROOT"

command -v docker >/dev/null || fail "docker is unavailable"
require_directory "$INGRESS_ROOT"
require_directory "$RELEASE_ROOT"
[[ -r docker-compose.yml ]] || fail "docker-compose.yml is absent"
[[ -r docker-compose.production.yml ]] || fail "docker-compose.production.yml is absent"

printf '%s\n' 'TSIRD Drought production release preflight (read-only)'
printf 'Application root: %s\nIngress root: %s\nServing release root: %s\n' \
  "$APP_ROOT" "$INGRESS_ROOT" "$RELEASE_ROOT"

docker compose "${COMPOSE_FILES[@]}" config --quiet
printf '%s\n' 'OK: production Compose configuration resolves.'

free_kib="$(df -Pk "$RELEASE_ROOT" | awk 'NR == 2 {print $4}')"
[[ "$free_kib" =~ ^[0-9]+$ ]] || fail "could not determine free space for $RELEASE_ROOT"
required_kib=$((MIN_FREE_GIB * 1024 * 1024))
if (( free_kib < required_kib )); then
  fail "free space is below ${MIN_FREE_GIB} GiB; retain current and rollback releases before promotion"
fi
printf 'OK: %.2f GiB free at serving release root (minimum %s GiB).\n' \
  "$((free_kib / 1024))e-3" "$MIN_FREE_GIB"

printf '%s\n' 'Running production services:'
docker compose "${COMPOSE_FILES[@]}" ps

api_container="$(docker compose "${COMPOSE_FILES[@]}" ps -q tsird-api)"
[[ -n "$api_container" ]] || fail "tsird-api is not running; do not promote a release"
mount_line="$(docker inspect "$api_container" --format '{{range .Mounts}}{{if eq .Destination "/data/drought/production-releases"}}{{.Source}}|{{.RW}}{{end}}{{end}}')"
[[ "$mount_line" == "${RELEASE_ROOT}|false" ]] || fail "tsird-api does not have the expected read-only release mount"
printf '%s\n' 'OK: tsird-api has the expected read-only release mount.'

printf '%s\n' 'PASS: narrow release-time delta check completed. This does not approve or activate a release.'
