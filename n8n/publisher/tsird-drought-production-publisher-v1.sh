#!/bin/sh
# Fixed-purpose manual publisher for an already-approved compact TSIRD drought
# release. It is intended to run inside the local n8n container via the
# Execute Command node, after this tracked copy is placed in that container's
# /workflows mount. It never accepts a release path, destination path, key
# path, shell fragment, or arbitrary remote command.
set -eu

STAGING_ROOT="/home/node/.n8n/tsird-drought-release-staging"
KEY_ROOT="/home/node/.n8n/tsird-drought-publisher-keys"
UPLOAD_USER="tsird-release-upload"
ACTIVATE_USER="tsird-release-activate"
RELEASE_ID=""
HOST=""

usage() {
  echo "Usage: $0 --release-id YYYY-MM-DDTHHMMSSZ[-suffix] --host production-vps-host" >&2
  exit 64
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --release-id)
      RELEASE_ID="${2:-}"
      shift 2
      ;;
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

printf '%s\n' "$RELEASE_ID" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z(-[a-z0-9][a-z0-9-]*)?$' || {
  echo "ERROR: release ID is invalid" >&2
  exit 64
}
case "$HOST" in
  ""|*[!A-Za-z0-9.-]*) echo "ERROR: production host is invalid" >&2; exit 64 ;;
esac

RELEASE_DIR="$STAGING_ROOT/$RELEASE_ID"
MANIFEST="$RELEASE_DIR/manifest.json"
UPLOAD_KEY="$KEY_ROOT/tsird-drought-release-upload"
ACTIVATE_KEY="$KEY_ROOT/tsird-drought-release-activate"
KNOWN_HOSTS="$KEY_ROOT/known_hosts"

for required in node ssh sftp grep mktemp; do
  command -v "$required" >/dev/null 2>&1 || {
    echo "ERROR: required command is unavailable: $required" >&2
    exit 69
  }
done
for required in "$MANIFEST" "$UPLOAD_KEY" "$ACTIVATE_KEY" "$KNOWN_HOSTS"; do
  [ -r "$required" ] || {
    echo "ERROR: missing or unreadable controlled publisher input: $required" >&2
    exit 66
  }
done

# Check the named, approved manifest and every allow-listed payload before any
# remote connection. Historical replay/provider geometries are permitted only
# under their fixed naming patterns; arbitrary files are never published. The
# VPS independently repeats the stronger release validator before it can
# change current.json.
RUNTIME_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$RUNTIME_DIR"
}
trap cleanup EXIT HUP INT TERM
chmod 700 "$RUNTIME_DIR"
RELEASE_FILE_LIST="$RUNTIME_DIR/release-files"
node -e '
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const [manifestPath, expectedId, outputPath] = process.argv.slice(1);
const required = [
  "status.json",
  "drought-evidence-summary.json",
  "drought-workspace-latest.json",
  "priority-replay-summary.json",
  "fews-net-context.json",
  "priority-replay-latest.geojson",
  "fews-net-context-latest.geojson",
];
const historical = /^(priority-replay-snapshot|fews-net-context-issue)-[a-z0-9][a-z0-9-]*\.geojson$/;
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
if (manifest.release_id !== expectedId || manifest.release_state !== "approved") {
  throw new Error("manifest does not name this approved release");
}
if (!Array.isArray(manifest.assets) || manifest.assets.length < required.length) {
  throw new Error("manifest does not have the minimum approved asset set");
}
const assetByPath = new Map(manifest.assets.map((asset) => [asset.relative_path, asset]));
if (assetByPath.size !== manifest.assets.length) throw new Error("manifest has duplicate asset paths");
for (const filename of required) {
  const asset = assetByPath.get(filename);
  if (!asset || !Number.isInteger(asset.byte_size) || !/^[a-f0-9]{64}$/.test(asset.sha256 || "")) {
    throw new Error(`manifest lacks a valid fixed asset record: ${filename}`);
  }
  const filePath = path.join(path.dirname(manifestPath), filename);
  const bytes = fs.readFileSync(filePath);
  const checksum = crypto.createHash("sha256").update(bytes).digest("hex");
  if (bytes.length !== asset.byte_size || checksum !== asset.sha256) {
    throw new Error(`local asset checksum does not match manifest: ${filename}`);
  }
}
for (const [filename, asset] of assetByPath) {
  if (!required.includes(filename) && !historical.test(filename)) {
    throw new Error(`manifest contains a non-publishable asset: ${filename}`);
  }
  if (!asset || !Number.isInteger(asset.byte_size) || !/^[a-f0-9]{64}$/.test(asset.sha256 || "")) {
    throw new Error(`manifest contains an invalid asset record: ${filename}`);
  }
  const filePath = path.join(path.dirname(manifestPath), filename);
  const bytes = fs.readFileSync(filePath);
  const checksum = crypto.createHash("sha256").update(bytes).digest("hex");
  if (bytes.length !== asset.byte_size || checksum !== asset.sha256) {
    throw new Error(`local asset checksum does not match manifest: ${filename}`);
  }
}
fs.writeFileSync(outputPath, ["manifest.json", ...assetByPath.keys()].sort().join("\n") + "\n", "utf8");
' "$MANIFEST" "$RELEASE_ID" "$RELEASE_FILE_LIST"

# The n8n data mount may not preserve Unix modes on the Windows host. Copy
# each credential to a private ephemeral directory before OpenSSH reads it.
cp "$UPLOAD_KEY" "$RUNTIME_DIR/upload_key"
cp "$ACTIVATE_KEY" "$RUNTIME_DIR/activate_key"
cp "$KNOWN_HOSTS" "$RUNTIME_DIR/known_hosts"
chmod 600 "$RUNTIME_DIR/upload_key" "$RUNTIME_DIR/activate_key" "$RUNTIME_DIR/known_hosts"

BATCH_FILE="$RUNTIME_DIR/upload.batch"
{
  printf 'mkdir /incoming/%s\n' "$RELEASE_ID"
  while IFS= read -r filename; do
    printf 'put %s /incoming/%s/%s\n' "$RELEASE_DIR/$filename" "$RELEASE_ID" "$filename"
  done < "$RELEASE_FILE_LIST"
} > "$BATCH_FILE"

# Strict host-key checking is intentional. The known_hosts file must be built
# from a fingerprint verified from an existing administrative VPS session.
SSH_OPTIONS="-o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$RUNTIME_DIR/known_hosts -o GlobalKnownHostsFile=/dev/null"
sftp $SSH_OPTIONS -i "$RUNTIME_DIR/upload_key" -b "$BATCH_FILE" "$UPLOAD_USER@$HOST"
ssh $SSH_OPTIONS -i "$RUNTIME_DIR/activate_key" "$ACTIVATE_USER@$HOST" "activate $RELEASE_ID"

printf '%s\n' "OK: uploaded and requested verified activation for $RELEASE_ID"
