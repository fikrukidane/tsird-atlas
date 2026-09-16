# TSIRD Drought Intelligence — staged production release plan

**Status:** proposed implementation plan, 2026-09-16
**Scope:** public experimental TSIRD Drought Intelligence and a separate,
protected Expert Evidence Review portal.
**Not in scope:** an official forecast, food-security classification, response
priority decision, allocation mechanism, or automated operational scoring.

## 1. Purpose and release principle

TSIRD may be publicly useful while it is still experimental.  The production
release must therefore make retained evidence, provenance, uncertainty, and
the route for expert participation visible without presenting a development
output as an authority or instruction.

The constrained VPS is a serving environment, not a data-engineering
environment.  It must not run n8n, download source archives, generate rasters,
build containers, or retain large processing caches.

## 2. What is being released

| Component | Public release decision | Boundary |
| --- | --- | --- |
| Atlas base map and established published layers | Existing/public Atlas scope | Retain current `/map/` same-origin routing and layer safeguards. |
| Drought Intelligence evidence views | Public experimental release | Show source, observation date, coverage and limitations. No combined drought score. |
| Retrospective Evidence Replay | Public experimental release | Retrospective only; neutral C1--C4 draft codes; not a priority decision or forecast. |
| FEWS NET context | Public provider-context release | Native provider geography and labels only; no downscaling/crosswalk to Tabias and no scoring effect. |
| Scenario Laboratory | Keep development/internal during the first public release | Unsaved discussion tool; it cannot configure or publish a model. |
| Expert Evidence Review | Production, invited reviewers only | Separate WordPress access control; responses are not public. |
| n8n, drought runner, raw source data and historical raster archives | Development only | No public endpoint, host mount or production schedule. |

## 3. Production architecture

```text
Development host
  n8n schedules + drought runner + source retrieval + processing + validation
       |
       | approved, compact versioned release only
       v
Production Publisher workflow (n8n)
       |
       | SFTP/SSH restricted to production release-data path
       v
Production VPS
  edge / web / API / MapServer / PostGIS serving stack
  current-release pointer -> verified compact evidence release

Separate production WordPress site
  protected Expert Evidence Review page + accounts + responses
```

Source control remains Git.  Build images and test static assets on the
development host or a CI builder, then publish versioned images to a registry.
The VPS pulls a prebuilt image only.  SFTP is reserved for narrowly scoped,
versioned release data and small reviewed WordPress custom assets; it is not a
replacement for source control and must never overwrite an active release in
place.

## 4. Phases and release gates

### Phase 0 — scope, owners and freeze

1. Name the two public surfaces: the experimental Atlas/Drought Intelligence
   experience and the protected Expert Evidence Review portal.
2. Assign owners for production access, WordPress reviewer accounts, data
   release approval, incident response and respondent privacy requests.
3. Freeze a first-release scope.  New indicators, forecasts, outlooks,
   operational scoring, and unscheduled retrieval jobs do not enter this
   release.
4. Record the initial public wording: experimental evidence platform; no
   forecast, official classification, allocation or operational directive.

**Gate:** written scope, named release approver, public wording approved.

### Phase 1 — deployment inventory and VPS capacity budget

Use the completed VPS inventory as the authoritative baseline.  Do **not**
repeat a full host discovery or re-run expensive inventory tasks.  Immediately
before a release, perform only a narrow delta check:

1. Confirm current free disk/RAM, the currently running services, and enough
   room for one incoming release plus one rollback release.
2. Confirm the existing reverse proxy/TLS, database/data-mount and backup
   arrangements have not materially changed since the completed inventory.
3. Identify the public Atlas hostname/path and the WordPress hostname/path;
   retain the `/map/`, `/map/ogc` and `/map/api/` contracts.
4. Confirm whether the existing production PostGIS/MapServer data already supports
   the intended public layers.  Do not assume a clean checkout creates the
   gazetteer or external spatial data.

**Gate:** capacity sheet confirms a release and one rollback can coexist.  If
not, reduce the first release to compact static/vector summaries instead of
moving raw raster or database history.

The tracked [release-time preflight](production-release-preflight.md) makes
this narrow delta check repeatable. It is read-only and is not a replacement
for the completed inventory.

### Phase 2 — turn recent development work into a release inventory

For each artefact, record its owner, source, intended public use, size,
refresh cadence, quality gate, public wording and rollback dependency.

The initial inventory includes:

- CHIRPS final/preliminary rainfall evidence and retained observation history;
- CLMS NDVI and SWI evidence metadata/views; degraded Copernicus inputs stay
  explicitly degraded and are not represented as drought conclusions;
- FAO WaPOR T/AETI as agricultural water-use/crop-activity context only;
- historical January--August 2026 retrospective replay snapshots and stored
  threshold traces;
- provider-issued FEWS NET Ethiopia native-FSC issues for January, February,
  April, June and July 2026;
- the candidate 2018--2025 same-calendar-month NDVI/WaPOR reference, labelled
  review-required and never used as an operational baseline;
- the 16-case August 2026 expert-review package, evidence limitations,
  screenshots and privacy/retention text.

**Gate:** every public item has a provenance label and an explicit statement of
what it must not be interpreted as.

### Phase 3 — create the production data-release contract

Create a single publishable release directory, for example:

```text
releases/<UTC-release-id>/
  manifest.json
  status.json
  drought-evidence-summary.json
  priority-replay-summary.json
  fews-net-context.json
  checksums.txt
```

The manifest must carry source and retrieval dates, spatial/time coverage,
processing/release version, readiness/quality state, file hashes, a prior
release ID and public caveats.  Only compact summaries, provider assets and
pre-generated display products belong here.  Raw rasters, n8n histories,
credentials, processing logs and temporary data do not.

The API/web layer reads the immutable `current` release only after all files
and checksums are verified.  A failed upload leaves the prior release live.

**Gate:** a local dry-run shows that an incomplete, stale, failed, degraded or
schema-incompatible release cannot switch `current`.

### Phase 4 — build the controlled n8n Production Publisher

1. Leave retrieval and processing schedules on the development n8n instance.
2. Add one distinct publisher workflow, with its own least-privilege production
   account, credentials and audit log.
3. Have the publisher run only after a declared source workflow has produced a
   validated release manifest.
4. Upload to `releases/<id>` via SFTP/SSH, verify remote checksums, then make
   the small atomic `current` change.
5. Start in **manual approval** mode.  A human approves a release after
   reviewing the manifest and availability status.  Automatic promotion can be
   considered later, product by product, after stable observed runs.
6. Send an alert on failed retrieval, validation, upload or switch; do not
   silently publish a partial or inferred replacement.

**Gate:** test promotion, simulated failed upload, rollback and notification
without changing the public `current` release.

### Phase 5 — package code without building on the VPS

1. Commit reviewed code and documentation to a release branch/tag in Git.
2. Run frontend/API checks locally, including `git diff --check` and the
   production localhost guard for served frontend changes.
3. Build Docker images locally/CI and publish immutable version tags to a
   registry.
4. On the VPS, set the three immutable image references in an untracked
   production image environment file, run the production-image configuration
   guard, then pull the prebuilt images and use a pinned Compose release
   manifest. Do not run image builds on the VPS. The production overlay removes
   `build:` from web/API/edge and excludes ETL from the default profile.
5. Retain the immediately prior image tag and release-data pointer for
   rollback; prune only confirmed superseded images/releases in accordance with
   the capacity budget.

**Gate:** source tag, image tag, release-data ID and deployed configuration are
recorded together in a release note.

### Phase 6 — deploy the protected Expert Evidence Review portal

1. Add the briefing explaining why the review exists: it tests local
   plausibility and missing/confounding context; it does not validate a model
   or produce a decision.
2. Add the reviewer guide, privacy/retention/withdrawal language and invitation
   template.
3. Place the portal at a production HTTPS URL under the agreed Tigray Drought
   menu, separate from the public Atlas maps.
4. Create a least-privilege reviewer role: access to the review and the
   reviewer's own responses only; no WordPress editing, user administration or
   visibility of other reviewers' submissions.
5. Use one-time password-set/reset links rather than reusing shared passwords.
6. Test login, case navigation, saving a draft, final response, revision
   history, export, withdrawal/correction handling and administrator access
   with a dedicated test account.

**Gate:** a test reviewer can complete the full path; an unauthenticated user
and a second reviewer cannot see a response.

The reusable participant-facing [briefing and invitation](expert-evidence-review-briefing.md)
are maintained with this release plan. They must be adapted with the approved
retention contact and individual password-set link before use.

### Phase 7 — deploy public experimental Atlas/Drought Intelligence

1. Deploy first to a non-public staging hostname using the production-shaped
   Compose configuration and a compact representative data release.
   The public-facing surface is `/map/drought/release/`; it reads only the
   approved-release API and deliberately shows an unavailable state rather
   than falling back to development endpoints.
2. Verify browser rendering under the final `/map/` path, same-origin API/WMS
   routing, map capabilities, selected bilingual search results, evidence
   panels, Priority Replay neutral labels, and FEWS NET compare mode.
3. Confirm public explanatory pages link to the model specification, source
   notes, FEWS NET attribution/context boundary, candidate-baseline limitation,
   and expert-review invitation.
4. Verify cache controls so the current interface is served after deployment;
   check with a normal browser load, not only cache-busted URLs.
5. Promote the exact tested image and release-data ID to the public VPS.

**Gate:** release approver confirms visual smoke test, route checks, freshness
status and disclaimer visibility on production.

Run the [public-release acceptance check](public-release-acceptance-check.md)
after activation. It is a read-only verification of the public viewer and the
approved asset boundary, not a promotion command.

### Phase 8 — invitation and monitored public launch

1. Invite a small first cohort using the approved email, live protected URL and
   individually created reviewer accounts.
2. Do not publish any reviewer identity or response.  Track invitations and
   completion separately from content.
3. Monitor page errors, storage, access failures, feedback export integrity and
   public data-release status during the first review window.
4. Record issues as documentation or change proposals.  Do not allow responses
   to automatically change thresholds, priority replay, provider context or
   public layers.

**Gate:** first cohort completes without privacy/access incidents and feedback
is exportable in the agreed structured format.

### Phase 9 — maintenance and later calibration review

1. Maintain a release ledger containing code tag, image tag, release-data ID,
   data manifest, approval, deployment time, verification results and rollback
   target.
2. Run the Production Publisher under manual approval until data contracts and
   operational experience justify a narrower automatic rule.
3. Review expert feedback in a documented workshop/process.  Separate:
   observations, disagreement, missing data, proposed tests, and any future
   model-change decision.
4. If a model revision is proposed, create a new draft/version and a separate
   retrospective review; never rewrite a released historical snapshot.

## 5. Mandatory safety and resource controls

- No public n8n UI, runner endpoint, Docker socket, credentials or raw data
  mount.
- No direct production data writes from ordinary source workflows.
- No automatic FEWS NET geometry retention or conversion to a Tabia class.
- No candidate 2018--2025 baseline activation in priority scoring.
- No production build, raster processing, archive retrieval or full database
  dump on the constrained VPS.
- One prior working code release and one prior data release remain recoverable.
- Release failures retain the previously served release and create an alert.
- Production logs are rotated and bounded; backup destination and restore test
  are documented before launch.

## 6. Decisions needed before execution

1. The existing Atlas target is `https://lab.tigrayinsights.net/map/`, served
   from `/opt/tigrayinsights/apps/tsird`; retain this route unless the sponsor
   later explicitly changes it.
2. The completed VPS inventory is the capacity baseline; use only the narrow
   release-time delta check in Phase 1.
3. Container image registry versus a constrained alternative transport.
4. WordPress production/staging location, account administrator and response
   retention/withdrawal policy.
5. First-release public layers and refresh cadence for each source.
6. Who approves a data release and who may use the emergency rollback path.

## 7. Definition of a successful first release

The public site serves the approved experimental evidence platform and
documentation from a compact, versioned release; the protected review portal
collects invited expert feedback; development n8n remains outside production;
the VPS runs only serving components; and any new evidence reaches production
only through an auditable, reversible, approved publisher release.
