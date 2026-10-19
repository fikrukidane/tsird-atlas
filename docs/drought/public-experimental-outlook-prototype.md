# Public Experimental Outlook prototype boundary

**Status:** controlled production interface prototype, 2026-10-18.

This is not a seasonal forecast release. It is a fixed, synthetic,
Woreda-shaped interface prototype intended to let collaborators review how a
future Woreda-scale seasonal-outlook context could be presented alongside
retained evidence.

The visible disclaimer is mandatory and must remain verbatim:

> Experimental Outlook prototype — for review only. Not for operational,
> public-safety, food-security, allocation, or response decisions.

## Technical boundary

- The public API accepts no Outlook run ID from a browser. It exposes only the
  fixed `synthetic-seasonal-outlook-review-20261018` record.
- It returns only `woreda_context` features. No native-grid cells, Tabia
  forecast, provider geometry, source URL, credential, raw input, live score,
  allocation tool, or survey response is served.
- The fixture stores deterministic synthetic probabilities against complete
  Tigray Woreda boundaries. It is marked synthetic, review-only, degraded and
  not provider-issued in its database provenance.
- It is separate from the approved evidence-release pointer. Publishing it
  does not activate, replace or relax validation for `current.json` or the
  automatic indicator pointer.
- `/map/api/drought/development/` and the development/admin Model,
  Scenario, and Pipeline Control routes are denied at the production edge.

## Removal and replacement

The prototype must be removed or replaced before any operational use. A real
provider product requires its own documented licence, provenance, issued and
validity dates, native geography, quality review and release approval. The
Expert Review Survey remains a separate protected deployment; no survey URL
is included in the Atlas.
