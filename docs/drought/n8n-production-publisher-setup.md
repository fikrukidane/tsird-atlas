# TSIRD manual Drought Production Publisher — local n8n setup

**Status:** tracked import template; inactive and not yet imported/configured.

This is the controlled transfer seam between the development environment and
the production VPS. It does not retrieve data, run the drought model, build an
image, or schedule any production action. It can be run only manually after a
named human approves a compact release package.

## What the publisher is allowed to do

The template accepts one UTC release ID, reads exactly these seven files from a
fixed local staging folder, uploads them through the SFTP-only account, and
then requests the forced `activate <release-id>` command through the separate
activation account:

```text
manifest.json
status.json
drought-evidence-summary.json
priority-replay-summary.json
fews-net-context.json
priority-replay-latest.geojson
fews-net-context-latest.geojson
```

The VPS activation utility performs the final approval/checksum verification
and changes `current.json` atomically. A rejected, incomplete, altered, or
unapproved package cannot become current. An upload failure leaves the
currently served release unchanged.

The workflow definition contains neither a production host nor credentials. Do
not add private keys to Git, workflow JSON, execution notes, or the release
package.

## Fixed local staging boundary

The current local n8n container already mounts
`C:\docker\data\n8n-data` as `/home/node/.n8n`. Use only this nested directory
for a compact, already approved package:

```text
C:\docker\data\n8n-data\tsird-drought-release-staging\<release-id>\
```

Inside n8n it is visible only as:

```text
/home/node/.n8n/tsird-drought-release-staging/<release-id>/
```

Do not mount the TSIRD repository, `data/drought`, a PostGIS volume, raw
rasters, source archives, or the local administrator SSH directory into n8n.
The small package reaches this folder only after the local build, validation,
and named approval described in the
[production-release contract](production-release-contract.md).

## One-time pinned-host setup and import

The built-in SFTP and SSH nodes in the installed n8n 2.6.4 release do not
expose SSH host-key verification. They must **not** be used for this production
transfer. The tracked publisher script instead uses the OpenSSH client with
`StrictHostKeyChecking=yes` and one locally pinned server host key.

1. From an existing authenticated VPS administrator session, obtain the ED25519
   host-key fingerprint:

   ```bash
   sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
   ```

   On the development host, obtain the candidate public key with
   `ssh-keyscan -t ed25519 <production-vps-host>`, compare its fingerprint to
   the VPS result, and only then save the verified key as
   `C:\docker\data\n8n-data\tsird-drought-publisher-keys\known_hosts`.
   Never accept an unverified `ssh-keyscan` result.
2. Place only the two dedicated, least-privilege private keys in the same
   `tsird-drought-publisher-keys` directory using these exact filenames:

   ```text
   tsird-drought-release-upload
   tsird-drought-release-activate
   ```

   The workflow copies them into a private temporary directory before OpenSSH
   reads them, then removes that temporary copy. Never put the normal VPS
   administrator key there. Keep access to the host directory limited to the
   local n8n administrator.
3. Copy the tracked fixed-purpose script into the existing n8n `/workflows`
   mount:

   ```powershell
   Copy-Item C:\docker\projects\tsird-atlas\n8n\publisher\tsird-drought-production-publisher-v1.sh `
     C:\docker\projects\n8n-platform\workflows\tsird-drought-production-publisher-v1.sh
   ```

   Its checksum should be recorded with the release ledger. Do not modify the
   deployed script without reviewing and merging a corresponding repository
   change.
4. Sign in to the local n8n UI as its administrator. Do not share the
   administrator password with a collaborator or place it in a document.
5. Import
   `n8n/workflows/tsird-drought-production-publisher-v1.development.json`.
   Confirm that it remains **inactive** and has only the manual trigger.
6. Set the two placeholders in **Set approved release ID before manual run**:
   the exact approved UTC release ID and the verified production VPS host name
   or address. Save without activating the workflow.

The first dry run should demonstrate the SFTP account sees only `/incoming`,
the activation account rejects arbitrary commands, and a mismatched server key
is rejected. Do not use the normal VPS administrator account or key.

## Each manual release

1. Build the package locally with the release builder.
2. Validate it locally, then have a named human run the approval command. The
   manifest must show `release_state: approved`.
3. Copy only that approved release directory into the fixed n8n staging
   directory above. Preserve all names and contents exactly.
4. In the manual workflow, replace the placeholder `release_id` with that
   exact directory name. Execute once; it has no schedule trigger.
5. Review the n8n execution result and the public-release acceptance check.
   Record the package ID, named approver, exact code/image release, result,
   and previous pointer in the private release ledger.

The workflow intentionally does not delete staging files, failed ingress
uploads, prior releases, source data, or any database content. Retention and
cleanup remain a separate, reviewed capacity task.

## Before the first real release

Perform a small, approved rehearsal package only after the production serving
stack is using the pinned release configuration. Verify the expected
unavailable/current-pointer behavior, a successful activation, a failed
package that leaves the pointer unchanged, and a rollback to the prior approved
package. This publisher does not authorize an image pull, service restart, or
public launch by itself.
