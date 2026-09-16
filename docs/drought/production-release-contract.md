# TSIRD Drought production-release contract

**Status:** implementation contract for a future, manual-approval Production
Publisher. It does not authorize a production connection or data transfer.

## Purpose

The development n8n instance may produce a compact, immutable public evidence
release only after source-specific processing has completed and a human release
approver has reviewed it. The contract keeps the constrained production VPS out
of retrieval, raster processing and n8n execution.

One release directory contains a `manifest.json` and the files named by that
manifest. The validator checks the local directory before any publisher is
permitted to use it.

```text
<release-id>/
  manifest.json
  drought-evidence-summary.json
  priority-replay-summary.json
  fews-net-context.json
  status.json
```

The example manifest is at
[`templates/drought-production-release-manifest.example.json`](templates/drought-production-release-manifest.example.json).

## States

| State | Meaning | Publisher action |
| --- | --- | --- |
| `validated` | Local checks, files and checksums passed. | May be inspected locally; cannot be staged or promoted. |
| `approved` | A named release approver reviewed the validated manifest. | Eligible for manual publisher execution. |
| `rejected` | The artifact must not be transferred. | Refuse. |

The release validator refuses a non-`approved` manifest unless invoked with
`--allow-validated`. That option is for local inspection only; it is not a
staging or production-publish authorization.

Every manifest names the preparer and preparation time.  An approved manifest
additionally names the independent release approver and approval time.

## Required evidence boundary

Every asset must declare:

- source/provider and source-observation window;
- retrieval timestamp and processing version;
- `validated` quality state;
- a clear interpretation boundary; and
- a SHA-256 checksum and byte size.

Allowed asset kinds are intentionally narrow: compact drought-evidence
summaries, retrospective replay summaries, provider-native FEWS NET context,
public status/provenance and static documentation. Raw rasters, raw downloads,
n8n execution history, credentials and arbitrary database exports are rejected
by policy and must never appear in a release manifest.

Provider-native FEWS NET content must retain its source geography and must say
that it is not transferred into a Tabia classification. Retrospective replay
content must say that it is not a forecast, official classification, allocation
or operational decision. Before packaging, the builder removes development-only
`planning_action`, priority class/rank, and rule-trigger fields from replay
geometry. It emits neutral retrospective draft codes (`C1`--`C4`) with retained
observation values and an explicit non-operational interpretation note. The
validator rejects a release if the removed fields or operational planning
phrasing are present.

## Read-only serving seam

The Atlas API exposes no public release until
`DROUGHT_PUBLIC_RELEASE_ROOT/current.json` points to an **approved** release.
Its public routes are deliberately separate from development routes:

```text
GET /map/api/drought/public/release
GET /map/api/drought/public/release/assets/<allow-listed-asset-id>
```

The first route returns redacted release metadata and asset provenance; the
second can serve only a manifest-listed JSON/GeoJSON file. Browser-provided
paths, release IDs and filesystem locations are never accepted. The production
API should receive a read-only mount of only the release root, for example:

```text
<host release root>:/data/drought/production-releases:ro
```

`current.json` is a small publisher-owned pointer containing the selected
release ID, activation time and prior release ID. It is written only after
remote verification; it must never point at a `validated` or `rejected`
manifest.

## Measured local staging sample

The first local staging release, `2026-09-16T140000Z-localstage`, contains six
compact metadata/display assets: rainfall evidence index, replay index, latest
replay GeoJSON, FEWS NET issue index, latest provider-native FEWS NET GeoJSON,
and release status. It measures about **10 MB** uncompressed. The two display
files compress to about **3.04 MB** (latest replay) and **0.51 MB** (latest
FEWS NET context) with gzip level 9.

This is an intentionally bounded first-release shape: one latest display
snapshot plus small historical indexes, not raw rasters or a full historical
geometry archive. It must be checked against the completed VPS capacity
baseline before production release.

## Local validation

From the repository root:

```powershell
python tools/validate_drought_production_release.py <release-directory>
```

The command verifies schema shape, safe relative paths, duplicate names, file
existence, exact size and SHA-256. It also requires the specified release
directory name to equal the manifest release ID.

No production host, SFTP endpoint, private key or password is accepted by this
command.

After a human has reviewed a validated local release, a separate explicit
command records the approval locally:

```powershell
python tools/approve_drought_production_release.py <release-directory> --approved-by "Full Name"
```

It first revalidates every payload checksum, then atomically changes only the
local manifest from `validated` to `approved`. It does not transfer or activate
the release. A content correction requires a new release directory rather than
rewriting an approved release.

## Manual publisher protocol

The tracked, inactive local n8n publisher template will, after its dedicated
least-privilege keys and a verified VPS host key are staged locally:

1. accept a supplied, already validated approved release ID;
2. stage it below `releases/<release-id>` on production;
3. verify the remote checksum list;
4. write a new small `current.json` pointer only after verification; and
5. retain the prior pointer for rollback.

It must not create a production dataset, execute a remote shell command,
retrieve source data, build an image, or alter an Atlas model configuration.
An upload failure leaves the current public release unchanged.

The template and its fixed OpenSSH publisher script are version-controlled at
`n8n/workflows/tsird-drought-production-publisher-v1.development.json` and
`n8n/publisher/tsird-drought-production-publisher-v1.sh`. They are not yet
imported or locally key-configured. The built-in n8n SFTP/SSH nodes are not
used because the installed version does not expose host-key pinning. The fixed
local staging boundary and one-time setup procedure are documented in
[n8n production publisher setup](n8n-production-publisher-setup.md).
