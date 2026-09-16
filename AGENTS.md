# TSIRD Codex Project Instructions

TSIRD — Tigray Insights Spatial Research & Development Platform (TSIRD Atlas).

Before changing the project, read:
- [Master context](docs/TSIRD_MASTER_CONTEXT.md) for architecture and source locations.
- [Project state](docs/TSIRD_PROJECT_STATE.md) for the inspected main commit, release distinctions, and verification limits.

Use the checked-out code and configuration to resolve conflicts with historical documentation. Keep these two documents current when architecture or release state changes; preserve TSIRD terminology and cite evidence rather than assuming deployment status.

## Safe development

- Work on a task branch; never commit directly to main or rewrite existing release tags. Keep changes scoped and preserve unrelated work.
- Preserve the `/map/` asset prefix, same-origin `/map/ogc` and `/map/api/` routes, edge fixed-mapfile handling, and loopback-only edge binding. Do not add localhost URLs or device-app triggers to production-served frontend files.
- Trace the active entry point in `ui/web/index.html` before editing frontend code. It uses classic browser scripts and global `ol`; preserve script order and do not assume legacy modules or registry copies are active.
- Preserve `MS_MAP_PATTERN` in `infra/mapserver/mapfiles/ms.config` and its Compose mount/environment wiring. Do not replace it with `MS_MAPFILE_PATTERN` (see troubleshooting Problem #13).
- Never commit real credentials, `.env.tsird`, source datasets, generated spatial outputs, database dumps, or backups. Do not copy deployment secrets into tracked mapfiles or documentation.
- Do not reset databases, remove volumes, overwrite source data, or deploy/restart production services without task authorization. Review ETL inputs, destinations, and CRS overrides before running data-changing scripts.
- Run checks appropriate to the change: `git diff --check` for docs; `python3 tools/validate_registry.py ui/web/data/atlas-registry.json` for registry changes (requires PyYAML); `bash scripts/check-no-localhost-in-production.sh` for served frontend changes and before release tags. The npm test command is a placeholder, not a test suite.
- For UI/WMS/API changes, verify affected behavior through `/map/` in a configured development stack. Check capabilities and rendered layers for WMS changes, and known bilingual results for search changes. Report unavailable data/services and pre-existing check failures honestly; never label unrun checks as passing.
