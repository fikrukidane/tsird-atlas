# TSIRD drought release activation account

This is a production-host operator recipe for the existing TSIRD deployment at
`/opt/tigrayinsights/apps/tsird`. It supports low-impact release promotion
without granting n8n a shell, Docker access, database access or write access to
the serving API mount.

## Root-only provisioning

Use the checked-in helper rather than manually composing a `Match` block or
editing `authorized_keys`. It is idempotent for the same keys, refuses to
replace a different existing key, validates the SSH configuration, and does
**not** reload SSH, pull an image, restart a container, transfer a release or
advance `current.json`.

Generate two separate public/private key pairs outside the repository and keep
the private material only in the development n8n credential store. From the
VPS root account, run:

```bash
cd /opt/tigrayinsights/apps/tsird
sudo scripts/provision-drought-release-accounts.sh \
  --upload-public-key /secure/path/tsird-release-upload.pub \
  --activate-public-key /secure/path/tsird-release-activate.pub
sudo sshd -t
# Keep this administrative session open, then reload only after the check passes.
sudo systemctl reload ssh
```

The script requires root because it creates system accounts and an SSH daemon
drop-in. It leaves the existing application account, existing untracked
backups, services, images and data unchanged. Do not use the normal VPS
administrator key for either publisher key.

## Two narrowly scoped accounts

1. `tsird-release-upload` is SFTP-only. It may upload a pre-approved release
   directory below `/srv/sftp/tsird-release/incoming/` and cannot access the
   application, Docker or serving release root. It is the only account with
   write access to that ingress.
2. `tsird-release-activate` has a dedicated SSH key with a forced command. It
   may only run `activate <release-id>`. The forced command invokes the checked
   in activation utility with fixed ingress and public-root paths; it does not
   provide an interactive shell. It belongs to a dedicated ingress-reader
   group with read/traverse access only, so it can checksum-validate an
   uploaded package but cannot add, replace or delete ingress files.

Use separate keys/credentials in n8n. Do not reuse the normal VPS
administrator key for either account.

## Serving and ingress locations

```text
SFTP ingress: /srv/sftp/tsird-release/incoming/<release-id>/
Serving root: /opt/tigrayinsights/apps/tsird/releases/drought/
API mount:     /data/drought/production-releases (read only)
```

The production Compose overlay mounts only the serving root into `tsird-api`.
The MapServer, API and browser never receive the SFTP ingress directory.

## Forced activation command

The provisioning helper installs a root-owned wrapper outside the upload
account's write paths at `/usr/local/sbin/tsird-activate-drought-release`:

```bash
#!/usr/bin/env bash
set -euo pipefail

command="${SSH_ORIGINAL_COMMAND:-}"
if [[ ! "$command" =~ ^activate\ ([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z(-[a-z0-9][a-z0-9-]*)?)$ ]]; then
  echo "Only: activate <release-id>" >&2
  exit 64
fi

exec /usr/bin/python3 /opt/tigrayinsights/apps/tsird/tools/activate_drought_production_release.py \
  "${BASH_REMATCH[1]}" \
  --incoming-root /srv/sftp/tsird-release/incoming \
  --public-root /opt/tigrayinsights/apps/tsird/releases/drought
```

In the activation account's `authorized_keys`, the helper forces that wrapper
and disables forwarding/TTY, for example:

```text
command="/usr/local/sbin/tsird-activate-drought-release",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty ssh-ed25519 AAAA... tsird-release-activate
```

The SFTP account uses `internal-sftp -u 027` with a chroot whose parent is
root-owned. Its `incoming` directory is setgid to the dedicated reader group:
new release directories and files remain uploader-owned, while the activation
account receives only the group read/traverse access required for validation.

## Publisher sequence

1. n8n generates and validates a local `validated` release.
2. A named human approver runs the local approval command, producing an
   immutable `approved` manifest.
3. n8n uploads the directory via the SFTP-only account to the ingress path.
4. n8n invokes the separate activation account with `activate <release-id>`.
5. The VPS validates checksums again, copies the package to the serving root,
   and atomically replaces `current.json`.
6. The API begins serving the new release. A failed validation/upload never
   changes `current.json`.

## Rollback

Rollback uses the same activation path with the prior immutable approved
release ID already retained in the serving root, or an operator atomically
restores the prior `current.json` after verifying its manifest. Do not delete
failed or prior releases during the first release window; prune only under the
separate capacity-retention policy.
