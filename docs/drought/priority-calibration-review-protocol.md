# Historical priority calibration review protocol

Status: **local development review procedure**. This protocol refines the
draft Seasonal Agricultural Stress & Response Priority matrix. It does not
create an official classification, allocation list, forecast, or published
decision.

## Why this is the next step

The current runner can reproduce a bounded January--August 2026 Tabia-level
historical plausibility replay from retained final CHIRPS evidence and static
population, cropland, and accessibility context. It is deliberately not
scheduled: a saved Model Studio draft can change replay classes, so a reviewer
must inspect the effect before another draft is generated.

The next operational question is therefore not "can the platform run again?"
but "do the transparent rules produce useful candidates for verification in
different seasons and locations?"

## Review material

For each selected month, reviewers use **Priority review** in `Compare` mode
and record observations for a purposeful set of Tabias:

1. Tabias classified Critical or High;
2. Tabias classified Moderate near the rainfall threshold;
3. contrasting Watch or Insufficient-evidence Tabias; and
4. locations from more than one zone and agricultural setting.

The selected-Tabia card supplies the TSIRD rule result, rainfall amount,
same-month baseline percentile, population/cropland deciles, accessibility
context, configuration version, and triggered rule. This makes each class
auditable rather than an unexplained score.

Where a FEWS NET issue is available, the side-by-side table shows only the
intersecting provider-native areas. It distinguishes the provider's **Current
assessment** from any **Projected assessment**, each with its stated period.
That comparison supports discussion of broad pattern consistency and gaps; it
does not transfer a FEWS NET class to the Tabia, provide a conversion between
the two methods, or change the TSIRD result.

## Questions for the review group

| Review question | What it tests |
| --- | --- |
| Does the rainfall percentile and seasonal window describe the observed local agricultural concern? | Monthly rainfall profile and threshold interpretation. |
| Does the planning cue describe an appropriate verification or coordination action? | Rule-to-action translation. |
| Are the population and cropland exposure conditions appropriate for this class? | Exposure thresholds; neither value is a needs estimate. |
| Does the accessibility tag add useful logistics context without being mistaken for road condition or passability? | Context wording and safe use. |
| If FEWS NET areas intersect, do they provide useful independent context or reveal a scale/timing difference? | Comparison usability; never a class crosswalk. |
| What local evidence would change confidence in the result? | Missing data and next-source priorities. |

Record the replay month, Tabia ID, active Model Studio version, reviewer,
evidence cited, finding, and proposed matrix change. Preserve disagreement;
it is evidence for the next version rather than an error to hide.

## Decisions after review

Only an administrator may save a new Model Studio draft. A revision must state
which monthly profile, factor condition, threshold, or planning cue changed and
why. The fixed historical replay runner is then manually invoked, and the new
draft is compared with the previous retained replay. It remains a draft-only
historical plausibility result.

No automatic recurring replay is enabled at this stage. A future local n8n
draft-run workflow is appropriate only after this review has accepted a model
version and its review process; it must call a fixed endpoint, retain
provenance, label its output as draft, and never self-publish.

## Conditions before an operational three-month draft

The historical review improves the current matrix, but it does not fill the
remaining data-engine gaps. Before a next-three-month planning draft can be
made available, TSIRD needs all of the following:

1. validated seasonal baselines and freshness handling for NDVI and WaPOR;
2. an approved, appropriately scaled seasonal-outlook data contract with
   issue date, validity window, provenance, and observed-only fallback;
3. a versioned decision-snapshot contract recording evidence cutoff,
   configuration version, quality gate, three-month window, and reviewer
   decision; and
4. practitioner review of selected Tabias across seasons and zones.

Until then, the platform should continue to present retained evidence,
historical draft replay, and provider context as planning-support material—not
an operational forecast or priority decision map.

## Baseline preflight

Pipeline Control reports the local NDVI and WaPOR months it can actually see.
This is an inventory, not a baseline calculation: retained 2026 observations
cannot stand in for a multi-year seasonal normal. Before requesting provider
history, the review group must agree the historical period, same-calendar-month
comparison method, coverage and quality rule, revision policy, and provider
access terms. The preflight does not contact providers, download data,
calculate anomalies, or alter the priority replay.

This refers to the Pipeline Control **local-inventory preflight**. It remains
separate from the provider metadata check described below.

The next fixed development check tests **metadata availability only** for the
provisional 2016--2025 candidate period. It inspects the configured CDSE NDVI
catalogue over the Tigray bounds and matching WaPOR T/AETI catalogue entries
for each calendar month. A complete result means only that candidate source
records exist; it does not approve the period, retrieve rasters, establish a
normal, or enable a priority class.

The first run found complete NDVI metadata coverage for 2016--2025, while
matching WaPOR T/AETI entries begin in 2018. The shared candidate is therefore
2018--2025. On 2026-09-14 the project sponsor recorded this as the provisional
eight-year candidate range, still subject to expert review of its adequacy and
seasonal method. No history has been retrieved or calculated into a baseline.
See the [availability preflight](seasonal-baseline-availability-preflight.md).
