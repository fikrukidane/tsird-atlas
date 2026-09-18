#!/bin/sh
# Fixed wrapper retained separately so the n8n Execute Command node has no
# inline JavaScript, untrusted path, remote command, or secret value.
set -eu
case "${1:-}" in
  --host)
    host="${2:-}"
    [ "$#" -eq 2 ] || { echo "Usage: $0 --host production-vps-host" >&2; exit 64; }
    ;;
  *)
    echo "Usage: $0 --host production-vps-host" >&2
    exit 64
    ;;
esac
case "$host" in ""|*[!A-Za-z0-9.-]*) echo "ERROR: production host is invalid" >&2; exit 64;; esac
exec node /workflows/tsird-drought-automatic-indicator-publisher-v1.js "$host"
