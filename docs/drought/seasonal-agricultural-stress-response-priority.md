# Seasonal Agricultural Stress & Response Priority — model specification

Status: **v0.1 development specification**. A read-only evidence-readiness
gate is implemented locally; no decision score, food-security classification,
or production workflow is implemented by this document. This specification is
the contract for the first draft engine and administrator-only Model Studio.

## Decision purpose and limits

The proposed product answers a narrower operational question:

> For the next three calendar months, which Tabias warrant the greatest
> agricultural-stress verification and response-planning attention, based on
> observed seasonal evidence, approved outlook context, agricultural exposure,
> and disclosed uncertainty?

It is **not** an IPC phase, hunger/famine forecast, humanitarian-access
assessment, yield forecast, or an official food-security classification. Those
claims need authoritative food-security, market, nutrition, displacement,
assistance, and access evidence that TSIRD does not currently have.

The model therefore publishes separate, reviewable components, a transparent
priority rule, and an action matrix—not an unexplained single risk number. A
supervisor can see why a Tabia is prioritized and can reject or annotate the
proposed priority.

This follows the useful part of FAO early-warning practice—linking monitored
agricultural drought evidence to early action—while retaining the IPC
convergence-of-evidence boundary. It does **not** substitute for an IPC
classification, which requires outcome evidence and formal multi-sectoral
analysis. See [FAO's early warning--early action guidance](https://www.fao.org/family-farming/detail/en/c/1637598/)
and the [IPC evidence-convergence protocol](https://www.ipcinfo.org/ipc-manual-interactive/ipc-acute-food-insecurity-protocols/function-2-classify-severity-and-identify-key-drivers/protocol-21-converge-evidence-using-the-ipc-analytical-framework/en/).

## Geographic and temporal contract

- **Tabia:** the primary priority result, keyed by `tsird_tabia_id` and the
  recorded Tabia-boundary version. It combines Tabia summaries with static
  context, but must not imply that a coarse source has Tabia-scale precision.
- **Woreda:** an automatic roll-up of Tabia results for regional planning, plus
  any provider outlook retained at Woreda scale. A Woreda-scale forecast may be
  displayed inside a Tabia only as labelled parent-Woreda context; it never
  becomes a Tabia forecast.
- **Forecast horizon:** every eligible run addresses the next three complete
  calendar months, starting on the first day of the next month. A decision
  issued in September therefore addresses October--December.
- **Monthly decision snapshot:** runs after the required source cutoff, rather
  than on an arbitrary calendar date. The run stores the cutoff, issue time in
  Addis Ababa time, input dates, horizon, and expiry/review date.
- **Outlook:** an approved provider-issued, one-to-three-month probability
  context. It informs response planning but does not override observed stress
  evidence.

If no suitable current outlook has passed provider, geographic-scale, and
validity checks, the engine may publish an **Observed stress & response
readiness** snapshot only. It must not call that snapshot a three-month
forecast or silently fill the outlook with a fixture.

## Initial components

| Component | First usable source | What is measured | Geographic caution | Role |
| --- | --- | --- | --- | --- |
| Rainfall condition | CHIRPS final monthly and rapid preliminary | Seasonal/rolling rainfall relative to its 1991–2020 reference | ~0.05° native grid; Tabia summaries retain coverage | Core observed-stress evidence. |
| Vegetation condition | CLMS NDVI v3 | NDVI anomaly/percentile against a seasonal local baseline | ~300 m grid; needs a completed baseline and fresh source item | Core observed-stress evidence after baseline validation. |
| Agricultural water-use | FAO WaPOR v3 T/AETI | Dekadal transpiration or anomaly, interpreted alongside crop calendar | ~100 m product; current absolute T is not stress without a seasonal baseline | Supporting evidence after baseline validation. |
| Soil-water context | CLMS SWI v4 | Broad root-zone wetness context | 0.1° (~12.5 km); not a Tabia-precise signal | Confidence/context only, not a Tabia discriminator. |
| Seasonal outlook | ICPAC/C3S approved product | Below/near/above-normal probabilities and lead time | Woreda or coarser | Planning context only. |
| Population baseline | WorldPop reference year | Modelled exposed population baseline | Not a census/current displacement count | Exposure scale. |
| Cropland baseline | ESA WorldCover 2021 class 40 | Reference cropland share/area | Not current cultivation or production | Agricultural relevance/exposure scale. |
| Road proximity | `TigrayRoads2006t`, ERA/TRRA Federal/Regional records | Straight-line proximity from Tabia point-on-surface | Historical network; not road condition, passability, or travel time | Delivery constraint tag. |
| Terrain complexity | TSIRD DEM and slope summaries | Relative terrain/slope constraint on field management and cultivability | Static terrain context; not a direct measure of farmer capacity or conservation investment | Sensitivity/context, subject to review. |
| Soil context | TSIRD soil reference layer and future reviewed soil sources | Broad water-holding and soil-condition context when attributes support it | Coarse/legacy source may not represent field conditions | Sensitivity/context, subject to review. |

## Transparent two-axis method

### Axis A — observed agricultural stress

This axis is a five-level evidence classification, not a probability of hunger:

1. **No stress signal** — valid evidence is near the seasonal reference.
2. **Watch** — one valid observed indicator is adverse.
3. **Elevated stress** — rainfall plus one agricultural/vegetation indicator are adverse.
4. **High stress** — two core observed indicators are persistently adverse,
   with adequate coverage and a valid seasonal baseline.
5. **Very high stress** — same as High, sustained across two completed
   monitoring periods and corroborated by a third independent source.

Rainfall can initially provide Watch-only status. Elevated-and-above require
fresh NDVI and/or baseline-normalized WaPOR evidence; they cannot be inferred
from the current absolute WaPOR T layer or a stale Copernicus receipt.
Coarse SWI may strengthen or weaken confidence but must not change Tabia class
by itself.

### Configurable initial rule set

Version 0.1 uses a transparent, configurable rule set rather than a trained
machine-learning model. The configuration records indicator inclusion,
standardization, relative weights, thresholds, missing-data rules, and the
translation from evidence to the five observed-stress levels. Exposure remains
visible as two independent deciles rather than being hidden inside the stress
score.

Terrain and soil may initially act only as disclosed **sensitivity modifiers**
or explanatory factors. They may not increase a priority result until their
meaning, direction, threshold, and practitioner justification have been
reviewed. This avoids assuming that steep terrain alone means lower resilience:
Tigray soil- and water-conservation structures and local farming practice can
materially alter that relationship.

### Axis B — exposed agricultural scale

Classify population and cropland **separately** into transparent deciles (the
existing 10-class exposure legends). The product presents the pair, for
example: `high cropland exposure / medium population exposure`; it does not
add them into an opaque number.

### Response-access tag

Road proximity is an operational flag:

- `near mapped Federal/Regional road`,
- `intermediate proximity`, or
- `far from mapped Federal/Regional road`.

It means only historical-network proximity. It must never be labelled aid
access, travel time, road condition, or passability.

## Action matrix

The user-facing priority map is a readable combination of the axes, with the
underlying components shown in its detail card:

| Observed stress | Exposure scale | Proposed planning cue |
| --- | --- | --- |
| No signal / Watch | Any | Monitor; verify data completeness. |
| Elevated | Lower | Local technical review and next-period check. |
| Elevated | Higher | Woreda planning review; inspect outlook and field information. |
| High / Very high | Lower | Targeted verification; assess whether local evidence misses population/cropland. |
| High / Very high | Higher | Priority candidate for coordinated field verification and response planning. |

Any `far` road-proximity tag is displayed beside the cue to support logistics
planning. It does not escalate the severity classification automatically.

## Model Studio and governance

The Model Studio is a separate **Priority** workspace tab. It is not an n8n
control screen and it cannot expose credentials or directly change source
schedules. The local development implementation has no authentication and
must therefore remain local-only; administrator-only access is required before
any non-local deployment.

### Administrator capabilities

- Read the plain-language model purpose, scope, exclusions, data sources,
  freshness rules, and interpretation guidance.
- Enable or disable an approved component; set its standardization method,
  weight, thresholds, and missing-data rule.
- Configure the response matrix, priority bands, Tabia-to-Woreda roll-up, and
  three-month decision-window rule.
- Save a named **draft** configuration, preview its effect against retained
  evidence, record rationale and reviewer notes, then publish a version only
  through an explicit administrator action.
- Compare two configurations and inspect which inputs explain changed Tabia
  results.

### Required provenance

Every draft or published result stores the model configuration ID and version,
component inputs, standardization values, quality-gate result, source run IDs,
boundary version, analyst/reviewer decision, issue time, and intended use
window. Published configurations are immutable; a revision creates a new
version. Future collaborators may be granted proposal/review access, but only
an administrator may publish a configuration or a decision snapshot.

### Current local implementation state

The local development database contains versioned draft configurations through
`20260912_add_seasonal_agricultural_priority_model.sql` and
`20260914_add_priority_model_studio.sql`. Model Studio saves an immutable new
draft version containing twelve monthly profiles, factor roles/conditions, and
plain-language priority rules; one draft can be marked active for the future
Priority Review runner. Saving does not calculate, publish, or alter a priority
map. The database reserves provenance fields for later snapshots and rejects
mutation/deletion of a published configuration. A score runner, snapshot
publication route, and real administrator authentication remain unimplemented.

It also retains January--August 2026 **historical calibration previews**. For
each one-month final-CHIRPS record, they preserve the same-month rainfall
percentile band, separate people/cropland deciles, road context, and a
coverage eligibility flag for every canonical Tabia. They deliberately do not
store a combined priority class. These previews are threshold-review material,
not as-issued forecasts, historical priority maps, or published decisions.
The local Priority tab displays a selectable preview month as a Tabia map and
returns these component details on selection; its legend explicitly calls the
colours rainfall-percentile calibration bands rather than priority classes.

### Historical priority replay runner

`20260915_add_priority_historical_replay.sql` and the fixed local runner
endpoint `POST /runs/priority-historical-replay/development-test` add the next
development step: a bounded January--August 2026 replay of the **active**
Model Studio draft. The job reads only retained final-CHIRPS Tabia evidence,
the static WorldPop population and WorldCover cropland references, and mapped
road-proximity context. It creates a new, draft-only snapshot for each retained
month and preserves the configuration version, source runs, target-month
profile, quality gate, planning action, and the exact triggered rule text for
each Tabia.

The first executable matrix is intentionally conservative and explicit:

- **Critical** — same-month rainfall percentile at or below 10, plus population
  or cropland decile 7 or above.
- **High** — rainfall percentile at or below 20, plus population or cropland
  decile 7 or above.
- **Moderate** — rainfall percentile at or below 33 where the higher rules do
  not apply.
- **Watch** — valid rainfall evidence without an adverse rainfall threshold.
- **Insufficient evidence** — missing or below-90% rainfall coverage; it is not
  ranked.

Accessibility is retained as an explanation and logistics tag only. It does
not yet change a class because mapped road proximity is not road condition,
passability, travel time, or a terrain model. No outlook, NDVI, WaPOR, official
assessment, intervention, livestock, water-service, or food-security result is
used by this first replay. It is therefore a **historical plausibility review**,
not an as-issued forecast, current priority product, allocation, IPC phase, or
food-security classification. It is deliberately not scheduled in n8n: a
reviewer must run and inspect it after changing the active configuration.

## User-facing Priority workspace

The local development UI separates **Drought conditions** from **Priority
planning**. The latter is available at `/map/drought/priority/`; it is a
focused historical-calibration review, not another conditions-map mode. A
separate **Model configuration** page at `/map/drought/priority/model/`
states the versioned draft inputs, exclusions, horizon, publication safeguard,
and outlook requirement. It is read-only until administrative editing and
authentication are designed.

The Priority review starts with one simple question: *was this Tabia's observed
rainfall unusually low for that calendar month?* It offers a month selector
for the retained January--August 2026 calibration records. A click outlines
the selected Tabia in yellow and reveals the supporting rainfall comparison
and contextual exposure values. The page calls these bands calibration
evidence—not a priority score, forecast, or food-security classification.

Once a reviewed configuration and draft engine are enabled, the Priority
workspace will provide:

- a Tabia map in ten ordered planning-priority classes and an optional Woreda
  roll-up;
- a horizon selector for months 1, 2, and 3 of the current decision window;
- an explicit issue date, valid planning window, evidence cutoff, next review
  date, and the model configuration version;
- a selected-Tabia explanation: observed stress, outlook context, people and
  cropland exposure, road tag, terrain/soil context where active, input dates,
  and any excluded or degraded evidence;
- comparison with the immediately preceding published run and a retained
  archive of past decision snapshots; and
- a conspicuous statement that the map supports targeting, verification, and
  monitoring—not automatic eligibility, allocation, IPC classification, or a
  food-security determination.

## Data-quality gates

No monthly priority snapshot may be published unless it records:

- source period, run ID, boundary version, coverage, quality, and freshness;
- at least one valid rainfall measurement; and
- the availability/missingness of NDVI, WaPOR, SWI, population, cropland, and
  road evidence.

If NDVI or SWI is degraded, as in the current development receipts, the map
must say `incomplete evidence` and cap the observed-stress class at Watch.
If a core input fails, retain the prior validated snapshot as historical only;
do not present it as the latest decision product.

### Local development readiness gate

The local Pipeline Control dashboard now calls a read-only gate before the
draft matrix work begins. It reports the latest run ID, source/observation
date, age, run status, mean Tabia coverage, boundary version, static-reference
year, and baseline readiness for each wired source. The gate currently never
publishes anything. It blocks a draft matrix if final rainfall is unavailable,
stale, degraded, or lacks usable Tabia coverage; it also caps the possible
observed-stress class at **Watch** until both fresh NDVI and a reviewed WaPOR
baseline are available. Its provisional development freshness thresholds are
45 days for final CHIRPS, 10 for rapid CHIRPS, 20 for NDVI/SWI, and 25 for
WaPOR. These are operational review thresholds, not scientific severity
thresholds, and must be validated with practitioners before a decision product
is enabled.

## Required build sequence

1. Establish seasonal baselines for NDVI and WaPOR and validate them against
   known agricultural seasons; current absolute values are insufficient.
2. Define v0.1 configuration defaults, including explicit terrain/soil
   treatment, and create the versioned Model Studio schema.
3. Add an approved Woreda-scale seasonal-outlook input, provenance, validity
   checks, and the observed-only fallback state.
4. Create a versioned monthly snapshot schema that stores each component,
   quality gate result, reviewer decision, reason text, and three-month use
   window.
5. Review the January--August 2026 historical plausibility replays produced by
   the fixed local runner; revise the explicitly recorded matrix thresholds.
6. Add a future n8n workflow only after review, calling a fixed runner endpoint
   to produce a draft snapshot and never self-publish it.
7. Review a small set of Tabias with Tigray agricultural and disaster-risk
   practitioners; revise thresholds before any decision-map release.
8. Add authoritative field/food-security/assistance evidence only under its
   provider permissions and governance, as a separate layer rather than a
   TSIRD-invented famine label.

The first implementation milestone is therefore a **draft observed agricultural
stress matrix** with explicit component values and quality gates. It is not yet
a food-insecurity forecast.
