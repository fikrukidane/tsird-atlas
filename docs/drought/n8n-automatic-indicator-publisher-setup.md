# TSIRD automatic retained-indicator publisher — local n8n setup

**Status:** tracked inactive template. It must be manually tested before its
schedule is enabled.

This workflow is the automatic counterpart to the manual reviewed-release
publisher. It has one narrow job: after the development evidence store has
updated, it builds a compact package containing the current six source-derived
Tabia summaries and six display-ready native-grid TIFFs, then publishes it only
when the package passes its technical gate and its fingerprint differs from
the last successful automatic publication.

It does not build or publish Priority Replay, Scenario Laboratory work,
Model Studio configuration, FEWS NET context, forecasts, model output, raw
provider archives, or source credentials. Those remain on the named-review
release path.

## Required local mounts

The existing n8n container already has its persistent data root mounted as
`/home/node/.n8n` and its tracked workflow folder as `/workflows`. Add exactly
one additional **read-only** bind mount to its local Compose service before
importing this workflow:

```text
C:\docker\data\drought\published:/opt/tsird-drought-native-rasters:ro
```

This is only the small, display-ready raster folder. Do not mount the broader
`data/drought` tree, source archives, the TSIRD repository, Docker socket, a
database volume, or an administrator SSH directory into n8n.

Copy these five tracked files into the existing read-only n8n `/workflows` mount
and install the pinned, build-only topology tool in n8n's persistent data
volume. Set `TSIRD_MAPSHAPER_BIN` on the n8n service to
`/home/node/.n8n/tsird-publisher-runtime/node_modules/.bin/mapshaper` before
activation. The publisher and Python
validator both read the same freshness contract; do not activate a workflow
with only a partial update. `mapshaper` changes only the release's display
geometry, preserving shared Tabia arcs; it never changes PostGIS or source
evidence geometry.

```powershell
Copy-Item C:\docker\projects\tsird-atlas\n8n\publisher\tsird-drought-automatic-indicator-publisher-v1.js `
  C:\docker\projects\n8n-platform\workflows\tsird-drought-automatic-indicator-publisher-v1.js -Force
Copy-Item C:\docker\projects\tsird-atlas\n8n\publisher\tsird-drought-automatic-indicator-publisher-v1.sh `
  C:\docker\projects\n8n-platform\workflows\tsird-drought-automatic-indicator-publisher-v1.sh -Force
Copy-Item C:\docker\projects\tsird-atlas\n8n\publisher\drought-indicator-freshness-contract.json `
  C:\docker\projects\n8n-platform\workflows\drought-indicator-freshness-contract.json -Force
Copy-Item C:\docker\projects\tsird-atlas\n8n\publisher\package.json `
  C:\docker\projects\n8n-platform\workflows\package.json -Force
Copy-Item C:\docker\projects\tsird-atlas\n8n\publisher\package-lock.json `
  C:\docker\projects\n8n-platform\workflows\package-lock.json -Force
docker compose -f C:\docker\projects\n8n-platform\compose.yaml exec -u node n8n `
  sh -lc 'mkdir -p /home/node/.n8n/tsird-publisher-runtime && cp /workflows/package.json /workflows/package-lock.json /home/node/.n8n/tsird-publisher-runtime/ && npm --prefix /home/node/.n8n/tsird-publisher-runtime ci --omit=dev --ignore-scripts'
```

The existing two restricted publisher keys and verified `known_hosts` file are
reused from `tsird-drought-publisher-keys`; no administrator key is involved.

## Import and first test

1. Import `n8n/workflows/tsird-drought-automatic-indicator-publisher-v1.development.json` and keep it inactive.
2. Set its `production_host` placeholder to the already verified VPS host or IP.
3. Execute the **Manual controlled run** once. It must either report
   `published` with a complete freshness declaration or `current` without moving the public pointer.
   Any missing raster, unavailable source, incomplete Tabia evidence, checksum
   mismatch, host-key mismatch, upload error, or VPS validation failure must
   fail while leaving the existing public indicator pointer untouched. Confirm
   that the generated `tabia-geometry.json` records `mapshaper@0.7.83`,
   `retain_vertices: 0.5%`, and the shared-topology note before activation.
4. Check the public Drought Intelligence page in both **Native raster** and
   **Tabia average** modes for each of the six indicator tabs.
5. Record the package ID, fingerprint, n8n execution result and previous
   pointer in the release ledger. Only then mark the workflow schedule-ready
   and activate it.

When active, its fixed schedule is 10:30 `Africa/Addis_Ababa` daily. This runs
after the currently scheduled source checks. It is intentionally a coalescing
check rather than six independent production transfers: new retained evidence
becomes public at the next run only if the entire six-stream technical gate is
complete. The persistent fingerprint prevents a duplicate daily release when
nothing changed.
