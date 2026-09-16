# Seasonal baseline acquisition design

Status: **decision recorded — 2018--2025 is TSIRD's provisional candidate
baseline range, agreed by the project sponsor on 2026-09-14.** It remains
reviewable through expert engagement; it is not a scientific certification or a
validated operational baseline. Following the sponsor's decision on 2026-09-14,
the fixed full-history retrieval and a separate observed-reference build are
authorized for local development. They cannot change Priority replay, publish a
layer, or create a drought/food-security classification. This turns the
metadata-availability result into a controlled implementation plan.

## Decision record and candidate scope

The 2026-09-14 decision adopts the common metadata-supported period
**2018--2025** as the working candidate. It supplies eight candidate years for
every calendar month for both configured sources:

| Evidence | One retained observation per month | Candidate retained units | Use in a future baseline |
| --- | --- | ---: | --- |
| CLMS NDVI v3 | nearest available 10-daily observation in the target month | 96 rasters | same-calendar-month vegetation reference after quality review |
| WaPOR v3 Level-2 T + AETI | third dekad, giving a complete month-end composite | 192 rasters (two bands × 96 months) | same-calendar-month agricultural water-use reference after quality review |

This is a common source-availability range, not a claim that eight years is
scientifically sufficient. The review group may revise it, choose a different
period, or limit the first baseline to agricultural-season months. Any such
change must be recorded as a baseline-method revision.

This decision authorizes one fixed local-development retrieval: 2018--2025 ×
all twelve calendar months, one strict in-month NDVI observation and WaPOR's
third dekad per slot. It also authorizes a review-required same-month median
and P20/P80 reference once the full matrix is retained. For a historical
reference-year observation, its comparison excludes that year (a seven-year
leave-one-year-out reference); a 2026 observation uses all eight candidate
years. It does not authorize a priority classification, forecast, publication,
or priority-model change.

## Completion record — 2026-09-14

The fixed 96-slot retrieval completed and produced the separate candidate
reference `tsird-seasonal-reference-2018-2025-v1`. The minimum rule was six
quality-approved years per Tabia/calendar-month. It retained **8,952** of the
8,976 possible Tabia-month rows for each indicator; 24 rows per indicator were
excluded rather than imputed. API history returns the candidate median and
percentile with a clear `candidate_review_required` state. For an observation
within 2018--2025, the displayed comparison excludes that observation's year,
giving a seven-year reference. This completion does not validate the reference
or permit any Priority Replay change.

## Evidence History map — 2026-09-14

The Drought Intelligence **Evidence history** map can now render retained NDVI
or WaPOR Tabia snapshots in a `Relative to reference` view.  For a selected
snapshot it shows the observed percentage deviation from the same-calendar-
month candidate median, with the valid reference-year count carried in each
Tabia feature. A historical 2018--2025 snapshot therefore uses the documented
seven-year leave-one-year-out comparison; a later observation uses up to all
eight retained candidate years. Candidate historical runs are served only as
pre-aggregated Tabia evidence, not raw-raster publication records. The view is
labelled `candidate_review_required` and remains outside Priority Replay,
forecasting, food-security classification, and response allocation.

## Bounded storage estimate

The estimate uses the eight locally retained 2026 samples, not advertised
provider file sizes:

| Retained source | Mean current Tigray-bounded raster size | 2018--2025 estimate |
| --- | ---: | ---: |
| NDVI | 1.68 MB each | 161 MB for 96 monthly observations |
| WaPOR T + AETI | 5.14 MB per band | 987 MB for 192 band files |
| **Source-raster subtotal** |  | **about 1.15 GB** |

This excludes small CSV/JSON summaries, temporary processing space, database
rows, and future source revisions. The current local storage safeguard reports
substantial free capacity, but the retrieval should still reserve at least
twice the source subtotal for safe temporary processing and retain a
pre-acquisition capacity receipt.

## Proposed staged process

1. **Method specification review.** Agricultural, remote-sensing, and
   disaster-risk reviewers assess the provisional 2018--2025 range;
   appropriate agricultural-season months; NDVI compositing choice; WaPOR
   dekad selection; quality/coverage rules; and what constitutes a valid
   reference value.
2. **Small pilot.** The fixed local-development runner may retrieve only the
   documented contrasting month/year matrix. Check provider revisions, CRS/grid consistency,
   Tabia coverage, quality flags, seasonal plausibility, and actual storage.
   Do not feed pilot values into Priority classes.
3. **Recorded technical gate.** The corrected strict-month pilot completed as
   retained review-only evidence on 2026-09-14. The sponsor has now authorized
   the fixed matrix below, with its storage guardrail retained.
4. **Bounded historical retrieval.** Process only the approved fixed month/year
   matrix through a fixed runner endpoint. Each run retains source timestamp,
   provider identifiers, checksums, boundary version, quality summary, and
   method version. It must fail closed on missing or changed source records.
5. **Reference build and validation.** Calculate a versioned, review-required
   observed reference only after the complete matrix is present. Compare its
   seasonal pattern with expert local knowledge before it is eligible as a
   draft-model input.

The initial bounded technical sampling frame and stop/revise criteria are in
[seasonal baseline pilot protocol](seasonal-baseline-pilot-protocol.md).
The proposed locally collaborative plausibility review is in the
[candidate reference review proposal](candidate-reference-review-proposal.md).

## Non-negotiable safeguards

- No recurring schedule may retrieve historical data.
- No default period or threshold is silently inferred from availability.
- A missing year/month remains missing; it is never imputed without a reviewed
  method and visible provenance.
- NDVI and WaPOR references remain separate evidence components.
- A candidate baseline cannot remove the development gate or raise Priority
  classes until it is reviewed and explicitly marked valid.
