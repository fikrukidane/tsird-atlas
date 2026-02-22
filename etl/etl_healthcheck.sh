#!/bin/sh
set -e

# 1) python runs
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found" >&2
  exit 1
fi
python3 -c "print('python_ok')" >/dev/null 2>&1 || { echo "python failed" >&2; exit 1; }

# 2) can resolve tsird-postgis
if ! getent hosts tsird-postgis >/dev/null 2>&1; then
  echo "cannot resolve tsird-postgis" >&2
  exit 1
fi

# 3) can open TCP connection to 5432
python3 - <<'PY'
import socket,sys
sock=socket.socket()
sock.settimeout(5)
try:
    sock.connect(("tsird-postgis",5432))
    sock.close()
except Exception as e:
    sys.exit(2)
sys.exit(0)
PY

# 4) /data is writable (touch staging healthcheck)
if [ ! -d /data/staging ]; then
  mkdir -p /data/staging || true
fi
touch /data/staging/.etl_healthcheck 2>/dev/null || { echo "/data/staging not writable" >&2; exit 1; }

echo "OK"
exit 0
