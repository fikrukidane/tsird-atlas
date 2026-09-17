#!/usr/bin/env bash
# Provision the two constrained production accounts used by the TSIRD drought
# release publisher. Run only as root on the production VPS after reviewing
# infra/host-nginx/tsird-drought-release-activation.md.
#
# This script does not transfer or activate a release, pull/build/restart
# containers, alter the current release pointer, or reload sshd.
set -euo pipefail

APP_ROOT="/opt/tigrayinsights/apps/tsird"
UPLOAD_USER="tsird-release-upload"
ACTIVATE_USER="tsird-release-activate"
SFTP_ROOT="/srv/sftp/tsird-release"
INGRESS_ROOT="${SFTP_ROOT}/incoming"
PUBLIC_ROOT="${APP_ROOT}/releases/drought"
SSHD_DROPIN="/etc/ssh/sshd_config.d/90-tsird-drought-release.conf"
ACTIVATOR="/usr/local/sbin/tsird-activate-drought-release"
UPLOAD_KEY=""
ACTIVATE_KEY=""

usage() {
  cat <<'EOF'
Usage: sudo scripts/provision-drought-release-accounts.sh \
  --upload-public-key /secure/path/tsird-release-upload.pub \
  --activate-public-key /secure/path/tsird-release-activate.pub

Creates only the restricted SFTP upload account, the forced-command activation
account, their key files, the SFTP ingress directory, the serving release root,
the activation wrapper, and an SSH configuration drop-in. It never reloads
sshd; validate and reload SSH manually from a separate administrative session.
EOF
}

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

while (($#)); do
  case "$1" in
    --upload-public-key)
      UPLOAD_KEY="${2:-}"
      shift 2
      ;;
    --activate-public-key)
      ACTIVATE_KEY="${2:-}"
      shift 2
      ;;
    --app-root)
      APP_ROOT="${2:-}"
      PUBLIC_ROOT="${APP_ROOT}/releases/drought"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      fail "unknown option: $1"
      ;;
  esac
done

[[ "${EUID}" -eq 0 ]] || fail "run as root"
[[ -d "$APP_ROOT" ]] || fail "application root is absent: $APP_ROOT"
[[ -r "$APP_ROOT/tools/activate_drought_production_release.py" ]] || \
  fail "activation utility is absent: $APP_ROOT/tools/activate_drought_production_release.py"
[[ -n "$UPLOAD_KEY" && -r "$UPLOAD_KEY" ]] || fail "a readable --upload-public-key is required"
[[ -n "$ACTIVATE_KEY" && -r "$ACTIVATE_KEY" ]] || fail "a readable --activate-public-key is required"
command -v ssh-keygen >/dev/null || fail "ssh-keygen is required"
command -v sshd >/dev/null || fail "sshd is required"

# Require one conventional public key per account. ssh-keygen also rejects
# malformed material before it reaches authorized_keys.
[[ "$(wc -l < "$UPLOAD_KEY")" -eq 1 ]] || fail "upload key must contain exactly one line"
[[ "$(wc -l < "$ACTIVATE_KEY")" -eq 1 ]] || fail "activation key must contain exactly one line"
ssh-keygen -lf "$UPLOAD_KEY" >/dev/null || fail "upload public key is invalid"
ssh-keygen -lf "$ACTIVATE_KEY" >/dev/null || fail "activation public key is invalid"

ensure_user() {
  local account="$1"
  local shell="$2"
  local home="$3"
  if ! id "$account" >/dev/null 2>&1; then
    useradd --system --create-home --home-dir "$home" --shell "$shell" "$account"
  fi
  usermod --lock "$account"
}

ensure_key() {
  local account="$1"
  local source_key="$2"
  local destination="$3"
  install -d -o "$account" -g "$account" -m 0700 "$(dirname "$destination")"
  if [[ -e "$destination" ]] && ! cmp -s "$source_key" "$destination"; then
    fail "existing key differs at $destination; rotate it through a reviewed account-change procedure"
  fi
  [[ -e "$destination" ]] || install -o "$account" -g "$account" -m 0600 "$source_key" "$destination"
}

ensure_user "$UPLOAD_USER" "/usr/sbin/nologin" "/var/lib/$UPLOAD_USER"
ensure_user "$ACTIVATE_USER" "/bin/bash" "/var/lib/$ACTIVATE_USER"

install -d -o root -g root -m 0755 /srv /srv/sftp "$SFTP_ROOT"
# The SFTP account writes only into this ingress.  The setgid group grants the
# separate forced-command activation account read/traverse access to completed
# packages, without granting it upload or general application access.
install -d -o "$UPLOAD_USER" -g "$ACTIVATE_USER" -m 2750 "$INGRESS_ROOT"
install -d -o root -g root -m 0755 "${APP_ROOT}/releases"
install -d -o "$ACTIVATE_USER" -g "$ACTIVATE_USER" -m 0750 "$PUBLIC_ROOT"
# Automatic indicator releases are source-derived retained evidence. The
# forced-command activation account alone creates and updates their versioned
# release directories and current pointer; MapServer reads them through its
# separate read-only bind mount as www-data, so the directory must be
# traversable by that serving process. The package contents remain immutable
# and the parent release root remains restricted to the activation account.
install -d -o "$ACTIVATE_USER" -g "$ACTIVATE_USER" -m 0755 "$PUBLIC_ROOT/indicators"

ensure_key "$UPLOAD_USER" "$UPLOAD_KEY" "/var/lib/$UPLOAD_USER/.ssh/authorized_keys"

# The activation key carries its force-command restriction itself. This avoids
# even a momentary unrestricted shell if sshd is reloaded between changes.
activate_authorized_keys="/var/lib/$ACTIVATE_USER/.ssh/authorized_keys"
activate_key_line="command=\"$ACTIVATOR\",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty $(cat "$ACTIVATE_KEY")"
install -d -o "$ACTIVATE_USER" -g "$ACTIVATE_USER" -m 0700 "$(dirname "$activate_authorized_keys")"
if [[ -e "$activate_authorized_keys" ]] && [[ "$(cat "$activate_authorized_keys")" != "$activate_key_line" ]]; then
  fail "existing activation key differs at $activate_authorized_keys; rotate it through a reviewed account-change procedure"
fi
if [[ ! -e "$activate_authorized_keys" ]]; then
  printf '%s\n' "$activate_key_line" > "$activate_authorized_keys"
  chown "$ACTIVATE_USER:$ACTIVATE_USER" "$activate_authorized_keys"
  chmod 0600 "$activate_authorized_keys"
fi

install -d -o root -g root -m 0755 "$(dirname "$ACTIVATOR")"
cat > "$ACTIVATOR" <<EOF
#!/usr/bin/env bash
set -euo pipefail

command="\${SSH_ORIGINAL_COMMAND:-}"
if [[ "\$command" =~ ^activate\\ ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z(-[a-z0-9][a-z0-9-]*)?)\$ ]]; then
  exec /usr/bin/python3 "$APP_ROOT/tools/activate_drought_production_release.py" \\
    "\${BASH_REMATCH[1]}" \\
    --incoming-root "$INGRESS_ROOT" \\
    --public-root "$PUBLIC_ROOT"
fi
if [[ "\$command" =~ ^activate-indicators\\ ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z-indicators)\$ ]]; then
  exec /usr/bin/python3 "$APP_ROOT/tools/activate_drought_production_release.py" \\
    "\${BASH_REMATCH[1]}" \\
    --incoming-root "$INGRESS_ROOT" \\
    --public-root "$PUBLIC_ROOT/indicators" \\
    --allow-auto-validated-indicators
fi
echo "Only: activate <release-id> or activate-indicators <release-id>" >&2
exit 64
EOF
chown root:root "$ACTIVATOR"
chmod 0755 "$ACTIVATOR"

install -d -o root -g root -m 0755 "$(dirname "$SSHD_DROPIN")"
temporary_dropin="${SSHD_DROPIN}.tmp"
previous_dropin="${SSHD_DROPIN}.previous"
had_previous_dropin=0
if [[ -e "$SSHD_DROPIN" ]]; then
  cp -- "$SSHD_DROPIN" "$previous_dropin"
  had_previous_dropin=1
fi
cat > "$temporary_dropin" <<EOF
# Managed by TSIRD drought release provisioning. Do not grant these users a
# general-purpose shell, Docker access, application write access, or a route
# to the serving API mount.
Match User $UPLOAD_USER
    ChrootDirectory $SFTP_ROOT
    ForceCommand internal-sftp -d /incoming
    PasswordAuthentication no
    PubkeyAuthentication yes
    AllowTcpForwarding no
    X11Forwarding no
    PermitTTY no
    PermitTunnel no

Match User $ACTIVATE_USER
    PasswordAuthentication no
    PubkeyAuthentication yes
    AllowTcpForwarding no
    X11Forwarding no
    PermitTTY no
    PermitTunnel no
EOF
chown root:root "$temporary_dropin"
chmod 0600 "$temporary_dropin"
mv -f "$temporary_dropin" "$SSHD_DROPIN"
if ! sshd -t; then
  if [[ "$had_previous_dropin" -eq 1 ]]; then
    mv -f "$previous_dropin" "$SSHD_DROPIN"
  else
    rm -f "$SSHD_DROPIN"
  fi
  fail "sshd rejected the installed drop-in; the previous SSH configuration was restored"
fi
rm -f "$previous_dropin"

printf '%s\n' 'PASS: restricted TSIRD drought release accounts and paths are provisioned.'
printf 'SFTP ingress: %s\nServing root: %s\n' "$INGRESS_ROOT" "$PUBLIC_ROOT"
printf '%s\n' 'No SSH reload, image pull, container restart, data transfer, or release activation was performed.'
printf '%s\n' 'From a separate administrative session, review `sshd -t` once more and reload SSH only when ready.'
