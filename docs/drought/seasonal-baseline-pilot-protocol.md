# Seasonal baseline pilot protocol

**Status:** Fixed local-development pilot runner implemented; it is manual and
unscheduled. No historical raster retrieval has been run under this protocol.

## Purpose

Test whether the provisionally selected **2018--2025** source history can be
retrieved and handled consistently before authorizing any full baseline build.
The pilot answers technical and methodological questions about source records,
units, geometry, quality, Tabia coverage, and storage. It does not calculate a
seasonal normal, anomaly, drought class, response priority, forecast, or
allocation recommendation.

## Fixed candidate matrix

The initial technical pilot is deliberately small: three evenly spaced years
and three contrasting calendar months.

| Candidate years | Candidate months | NDVI observations | WaPOR source bands | Total source files |
| --- | --- | ---: | ---: | ---: |
| 2018, 2021, 2025 | February, August, November | 9 | 18 (T and AETI) | 27 |

The month selection represents an early-, mid-, and late-year check. It is a
technical sampling frame, **not** an assertion about Tigray crop calendars or
the months that must define a future baseline. Practitioners may replace the
months before the pilot begins; a change must be recorded with its reason.

For NDVI, the selected provider observation timestamp must fall strictly within
the named calendar month. A provider query boundary that returns the first day
of the following month is a stop-and-correct condition, not an acceptable
substitute.

## What each pilot record must retain

- provider and product identifier, source timestamp/period, native resolution,
  revision identifier where supplied, URL identifier, and checksum;
- Tigray-bounded retained raster and the observed file size;
- CRS, scale/offset and nodata/quality metadata;
- canonical Tabia boundary version, count of Tabias with valid values, and
  coverage summary;
- processing method/version and a redacted run receipt; and
- an explicit label: `baseline_pilot_only`.

NDVI remains a vegetation observation. WaPOR T and AETI remain agricultural
water-use context. The pilot must not combine them, map them to FEWS NET, or
feed Model Studio or Priority replay.

## Acceptance questions

The pilot is only suitable to advance if review can answer all of these:

1. Is the intended month/year record still available from each provider and
   unambiguous enough to reproduce?
2. Do the retained rasters have the documented CRS, valid scale/nodata values,
   and a coherent Tigray extent?
3. Is Tabia coverage adequate and are gaps visible rather than imputed?
4. Are same-calendar-month and WaPOR dekad choices understandable to
   agricultural and remote-sensing reviewers?
5. Does measured storage remain within the recorded capacity budget?
6. Do reviewers agree to the next bounded retrieval matrix and a versioned
   baseline method?

A provider error, changed record, inadequate coverage, uncertain units, or
review disagreement is a **stop and revise** outcome, not a reason to fill
gaps or continue automatically.

## Implementation boundary

The runner accepts no user-supplied URL, date, path, SQL, model rule, or
publication instruction. It uses this fixed matrix only, runs manually in local
development, retains a receipt per source observation, and remains
unscheduled. Pilot source artifacts are labelled `baseline_pilot_only` and do
not replace the current NDVI or WaPOR map layers. A successful pilot merely
permits a documented method review; it does not mark the seasonal-baseline gate
ready.

## Review record

| Field | To be completed after the pilot |
| --- | --- |
| Pilot run identifiers | — |
| Provider records unavailable or revised | — |
| Coverage and quality findings | — |
| Storage measured | — |
| Reviewer decision | advance / revise / stop |
| Revision rationale | — |

## Run record

| Attempt | Date | Outcome |
| --- | --- | --- |
| 1 | 2026-09-14 | Rejected for review: the CDSE query treated the next-month midnight boundary as inclusive, selecting 1 March/September/December for February/August/November slots. The nine run rows are retained with the schema-supported `failed` status; artifacts remain pilot-only and are not baseline evidence. |
| 2 | 2026-09-14 | Completed with strict month-end query bounds: all nine NDVI timestamps and all nine WaPOR dekad starts align to 21 February, 21 August, or 21 November in 2018, 2021, and 2025. Status remains `completed_review_required`. |
