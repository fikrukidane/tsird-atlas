# Seasonal baseline availability preflight

Status: **local development metadata check, run 2026-09-14**. This records
provider catalogue availability only. It is not a downloaded archive, a
seasonal-normal calculation, an anomaly product, or a priority decision.

## Result

The fixed read-only preflight inspected the configured CDSE NDVI collection
over the Tigray request bounds and matching FAO WaPOR v3 Level-2 T/AETI
catalogue entries for every calendar month in the provisional 2016--2025
range. It requested no image pixels and retained no new source artifact.

| Source | 2016--2025 availability | Common usable period | Interpretation |
| --- | --- | --- | --- |
| Copernicus CLMS NDVI v3 | All twelve calendar months have at least one catalogue item in every year. | 2016--2025 is available from this source. | Candidate availability is complete; it does not establish a valid vegetation baseline. |
| FAO WaPOR v3 Level-2 T/AETI | All twelve calendar months have matching T/AETI catalogue entries for 2018--2025; 2016--2017 are absent. | 2018--2025. | The shared candidate period is eight years, not ten. Its adequacy needs agricultural and remote-sensing review. |

Therefore, **2018--2025** is the common metadata-supported candidate range
for a like-for-like NDVI/WaPOR baseline design. It is deliberately a proposal,
not a default: a reviewer may choose a different period, exclude disrupted
years, or decide that eight years is insufficient.

## Decision recorded

On 2026-09-14, the project sponsor selected **2018--2025 (eight calendar
years)** as TSIRD's provisional candidate baseline range. The decision is based
on the shared metadata availability window above and is deliberately reviewable
as practitioners and subject-matter experts engage. It does not certify
scientific adequacy, authorize bulk acquisition, or make a baseline
operational. Any later change to the period or eligibility rules must be
recorded as a revision.

## What must be agreed before retrieval

1. whether 2018--2025 is scientifically adequate for each indicator and crop
   season, including treatment of anomalous or disrupted years;
2. the same-calendar-month/dekad aggregation method, including how 10-daily
   NDVI and dekadal WaPOR records align;
3. minimum Tabia coverage, quality flags, missing-data rule, and source
   revision policy;
4. the exact retained artifact and storage budget; and
5. the review and versioning path before any baseline can influence a draft
   priority class.

Only after that agreement should TSIRD perform a bounded historical retrieval
and baseline build. Even then, the result must remain a reviewed development
input until practitioners validate it against local agricultural seasons.

The resulting candidate scope, current storage estimate, and staged retrieval
controls are set out in the [acquisition design](seasonal-baseline-acquisition-design.md).
