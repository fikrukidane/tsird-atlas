# Public Drought Workspace: Development-Parity Contract

## Purpose

The public TSIRD drought workspace is an experimental, collaborative evidence
environment.  It must let practitioners explore the same retained evidence
experience available in development, while keeping only the operations that
would change evidence, configuration, release state, or a future prediction
out of production.

It is **not** a reduced, separate map viewer.  Its implementation must reuse
the Atlas map shell, controls, Drought Dashboard, priority controls and page
route hierarchy used in development.

## Route and interaction contract

| Route | Production expectation |
| --- | --- |
| `/map/` | The existing Atlas landing page, layers, TOC, search and tools. |
| `/map/drought/` | The same Atlas header, map, Phase 3 search/measurement toolbar, TOC, Drought Dashboard and indicator modes as development.  Its map data are the approved-release summaries, not development services. |
| `/map/drought/release/` | A clearly labelled retained-evidence replay view using the same Atlas map shell and replay interaction. |
| `/map/drought/priority/` | The same review-month selector, FEWS NET issue selector, replay/context/compare control, click explanation and legend used in development, using only approved replay and provider assets. |
| `/map/drought/priority/scenario/` | The same candidate-review presentation and discussion controls, read-only/unsaved in production. |
| `/map/drought/priority/model/` | The same readable model-information presentation, but without save, activation or editable threshold controls. |
| `/map/drought/control/` | A clear development-only notice.  It must not reveal pipeline, credential, runner or storage controls. |

## What remains available

- Every approved, retained Tabia indicator summary and its source metadata.
- Map search, zoom, map click, Tabia evidence details, legends and the
  standard Atlas navigation and TOC.
- Latest and retained historical evidence that has been included in the
  approved release package.
- Historical replay review, provider-native FEWS NET context, and comparison
  without colour blending.
- The public candidate-review and model-method explanations.

## What remains development-only

- n8n, retrieval, ETL, raw rasters/source archives, runner status and storage
  control.
- Any model save/activation, scoring, forecast generation, priority publication
  or release activation action.
- Evidence that has not been explicitly included in an approved release.

## Data adapter rule

Production must call only `/map/api/drought/public/...` routes backed by the
approved release directory.  A public adapter may provide the response shapes
expected by shared browser components, but it must never proxy or fall back to
`/drought/development/...`, a raw raster, a development database query, or a
local n8n service.

If a development control requires a retained record that has not yet been
packaged, production must show an honest `not included in this release` state;
it must not remove the control or silently substitute another datum.

## Release acceptance gate

Before a production image is proposed, compare development and production on
the same routes and confirm all of the following:

1. The shared Atlas shell, header, map, Phase 3 toolbar, TOC and dashboard
   layout are visibly the same.
2. Every public indicator button renders the approved Tabia layer, supports
   selection, and reports the corresponding released evidence.
3. Priority Review has the review-month, FEWS NET issue and map-display
   selectors, click detail and unblended Compare view.
4. Scenario and model pages retain their development explanatory structure;
   unavailable write actions are clearly read-only, not replaced with a
   different product.
5. All production requests remain under `/map/api/drought/public/`, apart
   from the established Atlas search/boundary and OGC routes.
6. No wording presents the experimental evidence as an official forecast,
   food-security classification, allocation recommendation or operational
   decision.
