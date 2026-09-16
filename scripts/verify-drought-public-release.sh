#!/usr/bin/env bash
# Read-only acceptance check for the TSIRD public drought release surface.
# Usage: verify-drought-public-release.sh [--expect-unavailable] <origin>
set -euo pipefail

expect_unavailable=false
if [[ "${1:-}" == "--expect-unavailable" ]]; then
  expect_unavailable=true
  shift
fi
[[ $# -eq 1 ]] || { echo "Usage: $0 [--expect-unavailable] <origin>" >&2; exit 64; }
origin="${1%/}"
[[ "$origin" =~ ^https?://[^[:space:]]+$ ]] || { echo "Origin must be an http(s) origin" >&2; exit 64; }

page_url="$origin/map/drought/release/"
api_url="$origin/map/api/drought/public/release"
page_body="$(curl --fail --silent --show-error "$page_url")"
grep -Fq 'TSIRD Drought Evidence Release' <<<"$page_body" || { echo "FAIL: release page is not the expected viewer" >&2; exit 1; }

if "$expect_unavailable"; then
  status="$(curl --silent --show-error --output /tmp/tsird-drought-release-check.json --write-out '%{http_code}' "$api_url")"
  [[ "$status" == "404" ]] || { echo "FAIL: expected 404 for no approved release, got $status" >&2; exit 1; }
  grep -Fq 'release.js' <<<"$page_body" || { echo "FAIL: public release viewer script is not present" >&2; exit 1; }
  echo 'PASS: viewer is available and correctly refuses development fallback while no approved release exists.'
  exit 0
fi

metadata_file="$(mktemp)"
trap 'rm -f "$metadata_file"' EXIT
curl --fail --silent --show-error "$api_url" >"$metadata_file"
python3 - "$metadata_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
if payload.get("schema_version") != "tsird-drought-public-release.v1":
    raise SystemExit("FAIL: unexpected public release schema")
if not isinstance(payload.get("release_id"), str) or not payload["release_id"]:
    raise SystemExit("FAIL: release ID is missing")
assets = payload.get("assets")
if not isinstance(assets, list) or not assets:
    raise SystemExit("FAIL: public release assets are missing")
required = {"priority-replay-latest", "fews-net-context-latest"}
found = {item.get("asset_id") for item in assets if isinstance(item, dict)}
if not required.issubset(found):
    raise SystemExit("FAIL: required public map assets are missing")
for item in assets:
    if not isinstance(item, dict) or not isinstance(item.get("url"), str) or not item["url"].startswith("/map/api/drought/public/release/assets/"):
        raise SystemExit("FAIL: manifest exposes an invalid public asset URL")
print(payload["release_id"])
PY

release_id="$(python3 - "$metadata_file" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["release_id"])
PY
)"

while IFS=$'\t' read -r asset_id url; do
  [[ -n "$asset_id" && -n "$url" ]] || continue
  curl --fail --silent --show-error "$origin$url" >/dev/null
  if [[ "$asset_id" == "priority-replay-latest" ]]; then
    curl --fail --silent --show-error "$origin$url" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
for feature in payload.get("features", []):
    properties = feature.get("properties", {})
    forbidden = {"planning_action", "priority_class", "priority_rank", "triggered_rules"} & set(properties)
    if forbidden or "retrospective_draft_code" not in properties:
        raise SystemExit("FAIL: public replay exposes internal fields or lacks neutral draft code")
text = json.dumps(payload).lower()
if "immediate verification" in text or "coordinated response planning" in text:
    raise SystemExit("FAIL: public replay includes operational wording")
'
  fi
done < <(python3 - "$metadata_file" <<'PY'
import json, sys
for asset in json.load(open(sys.argv[1], encoding="utf-8"))["assets"]:
    print(f"{asset['asset_id']}\t{asset['url']}")
PY
)

echo "PASS: approved public release $release_id and all manifest-listed assets passed acceptance checks."
