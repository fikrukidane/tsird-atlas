# Candidate reference review proposal

Status: **proposed review protocol — not yet convened or endorsed by any
external institution.**

## Purpose

This protocol reviews TSIRD's retained 2018--2025 same-calendar-month NDVI and
WaPOR reference as **observed agricultural context**. It does not validate a
drought classification, food-security classification, forecast, allocation,
or response-priority decision. Its immediate purpose is to determine whether
the candidate reference is seasonally and locally plausible enough to remain
visible in Evidence History, and which parts (if any) could later be tested in
a transparent draft planning model.

The protocol is intended for future collaboration with relevant Tigrayan
institutions and practitioners, such as the Tigray Disaster Risk Management
Commission, Tigray Meteorological Service, agricultural specialists, Woreda
and Tabia extension practitioners, and independent technical reviewers. Their
potential participation is a proposal, not a claim of current approval or
partnership.

## Review sample agreed in principle

The first workshop will use **14 geographic Tabia cases** plus two diagnostic
cases (**16 cases in total**). Final Tabia names and identifiers must be selected with local reviewers
from the canonical TSIRD boundary set and recorded before analysis.

| Group | Cases | Selection intention |
| --- | ---: | --- |
| Wetter western agricultural setting | 1 | A comparatively wetter agricultural Tabia, used to test whether the reference behaves sensibly in a different rainfall and production context. |
| Central highlands | 3 | Three Tabias representing meaningful variation in elevation, production setting, and seasonal response. |
| Eastern low-rainfall setting | 5 | Five Tabias with locally recognised low-rainfall conditions. |
| Southern / southeastern setting | 5 | Five Tabias reflecting southern or southeastern conditions and seasonal patterns. |
| Apparently severe 2026 divergence | 1 | A case selected because observed 2026 evidence diverges strongly from its same-month reference. |
| Contradictory evidence | 1 | A case selected because rainfall, NDVI, and/or WaPOR do not tell a consistent story. |

The geographic sample is deliberate, not statistically representative. It is a
structured plausibility and usability review. A later, separately approved
validation plan may use a larger or random/stratified sample.

## Required evidence packet per case

Each case receives a short, reproducible evidence packet:

1. Tabia identity, Woreda, geographic group, and the selected calendar month.
2. Observed rainfall relative to its CHIRPS normal.
3. Observed NDVI and WaPOR value, same-month candidate median, percentage
   deviation, valid reference-year count, coverage, and quality status.
4. A small history plot covering the selected month across 2018--2026.
5. Source/provenance record, including whether WaPOR is near-real-time or
   final.
6. Available independent local context: crop stage, rainfall onset/cessation,
   planting, pasture, water availability, hail/pests, irrigation, access, or
   other event information. Missing context must be stated as missing.

## Review questions

For every case, reviewers record answers to the following questions:

1. Is this calendar month agriculturally meaningful for this Tabia?
2. Is the same-month observed reference plausible to local experience?
3. Do rainfall, vegetation, and crop-water-use evidence converge, partially
   converge, or contradict one another?
4. If they differ, what plausible explanation should be investigated?
5. Is the evidence fit only for display, conditionally eligible for a future
   draft rule, or unsuitable for this month/setting?
6. Which additional local data would be required before relying on it?

## Evidence interpretation safeguards

- A low NDVI or WaPOR value is not itself crop failure, household food
  insecurity, or response priority.
- A rainfall deficit can be buffered or amplified by timing, soil moisture,
  irrigation, crop stage, management, terrain, and other local factors.
- A disagreement between indicators is a finding to explain, not an error to
  average away.
- Insufficient coverage or fewer than six valid reference years produces an
  evidence-gap state, never an inferred priority.
- Historical 2018--2025 cases use a seven-year leave-one-year-out comparison;
  later observations use up to all eight candidate years.
- The reference remains `candidate_review_required` until a recorded review
  decision changes that status.

## Pre-committed review safeguards

The following safeguards are fixed before any workshop interpretation. They
respond to known limits in historical remote-sensing evidence; they do not
turn the workshop into a validation study.

- Reviewers assess local and seasonal **plausibility**, not predictive or
  scientific validation.
- Each case records a Tabia-year conflict/access flag. Where a review identifies
  a 2020--2022 or other disruption that could affect agricultural observations,
  TSIRD will show a clearly separate conflict-excluded sensitivity view only
  when at least six valid reference years remain. The retained eight-year
  candidate reference is not silently overwritten.
- NDVI and WaPOR are related land-surface observations, not independent votes.
  Agreement may motivate investigation; it must not be counted twice or
  averaged into a priority score.
- Review displays state the valid reference-year count and use comparison/rank
  language appropriate to a small candidate reference, rather than implying
  false precision from a percentile alone.
- Every evidence packet records provider product/version, coverage and quality
  status, plus known land-cover, irrigation and crop-calendar context where
  available.
- Reviewers use the questions above as a pre-committed rubric and record
  initial assessments independently before resolving disagreements. The record
  preserves disagreements, missing context and the rationale for every
  conclusion.
- The purposeful 16-case sample is for usability and plausibility discussion;
  it cannot be used to estimate regional prevalence. The initial August 2026
  snapshot is likewise not evidence for other months without separate review.

## Scenario Laboratory

Model Studio exposes the same fixed shortlist in a bounded **Scenario
Laboratory**. Its sliders test transparent, client-side discussion assumptions
against retained August 2026 evidence only. A local confounder review must be
explicitly cleared before the laboratory displays an interpretable signal.
The laboratory does not save a setting, alter the active model matrix,
recalculate Priority Replay, create a priority class, or recommend a response.
It is an aid for structured expert discussion, not a calibration or scoring
mechanism.

## Decision outcomes

The review group may select one outcome for each indicator/month/setting:

| Outcome | Meaning | Platform consequence |
| --- | --- | --- |
| Retain for observed context | Plausible enough for transparent historical display and explanation. | Evidence History continues to show it. |
| Conditionally test in a draft rule | Specific months, thresholds, and safeguards are documented for a non-published experiment. | A separate Model Studio scenario may be configured; it cannot publish automatically. |
| Revise or exclude | The period, method, interpretation, or local applicability needs change. | Preserve raw evidence and rationale; do not use it in a draft rule. |

No decision outcome authorizes IPC/FEWS NET classification, a forecast,
allocation, an automatic response action, or a published priority map.

## First review output

The workshop should produce a versioned Candidate Review Record containing:

- selected case identifiers and reasons for selection;
- reviewer roles and participating organizations, only with their consent;
- indicator/month applicability notes;
- agreements, contradictions, and unresolved data gaps;
- any candidate rules explicitly approved for later draft testing;
- a decision on whether the 2018--2025 reference remains display-only,
  becomes eligible for a bounded model experiment, or requires revision.

The first reproducible technical shortlist is recorded in the
[provisional selection register](candidate-reference-review-selection-register.md).
