# Public performance budget and measurement harness

Status: measurement foundation for the staged modernization of the public
atlas and drought workspace. It is a gate, not an optimisation. Nothing here
changes the site; it only measures it and says pass or fail.

## What is committed here

| File | Purpose |
| --- | --- |
| [`tools/performance-budget.json`](../../tools/performance-budget.json) | The budget: network profiles, viewports, per-page targets, and what counts as an application request. |
| [`tools/measure_public_performance.py`](../../tools/measure_public_performance.py) | The harness: drives a real browser, applies the fixed profile, records transfer bytes over CDP, and times the functional check. |
| [`baseline/20261011-manual-instrumentation.json`](baseline/20261011-manual-instrumentation.json) | The reference state of production on 11 October 2026, captured before the harness existed. |
| `baseline/<timestamp>-<page>-<profile>-<viewport>.json` | Archived harness runs, written by `--archive`. |

## The fixed test profile is a benchmark, not a claim

`slow-4g` is 1.6 Mbit/s down, 750 kbit/s up, 150 ms latency, with a 4× CPU
slowdown. It is a repeatable engineering benchmark used so that two runs can be
compared. It is **not** a description of any particular connection in Tigray,
and no public claim should be made from it. Keep the same profile across stages,
or the comparison means nothing. `regular-3g` is recorded for contrast and is
never used for pass or fail.

## Stage 1 acceptance criteria

| Measure | Baseline, 11 Oct 2026 | Stage-1 target | Mode |
| --- | --- | --- | --- |
| Critical application path before first usable interaction | not separable; whole load was 9.54 MB | **≤ 400 KB** | enforce |
| Functional check: select a visible Tabia and read back its values | **fails**, the boundary route returns HTTP 503 | **≤ 3 s** on `slow-4g` | enforce |
| Total cold application transfer | 9.54 MB | **≤ 1.5 MB** | enforce |
| Application requests, excluding basemap tiles | 47 of 72 | **≤ 15** | enforce |
| Basemap tile requests | 25 | recorded, no target | record |
| Repeat visit transfer and interaction time | not measured | recorded, expected to fall sharply once release-ID assets are immutable | record |

Why 400 KB and 3 seconds fit together: at 1.6 Mbit/s a browser moves roughly
200 KB per second. Three seconds minus connection setup and first-byte time
leaves about 2.4 seconds of transfer, which is about 480 KB. A 400 KB critical
path leaves margin for TLS, DNS and script execution on a throttled CPU. The
earlier pairing of 1.5 MB with 3 seconds was arithmetically impossible, which is
why the budget separates the critical path from the total.

Two constraints that sit outside the measured numbers:

- The published display geometry may be rounded and simplified, but only with
  topology preserved, and it must be versioned by release ID or content hash so
  that immutable caching stays correct.
- The analytical geometry in PostGIS, which the Tabia zonal statistics run
  against, is never simplified. Display changes must not change evidence.

The application-byte measures include first-party TSIRD responses and exclude
basemap tiles and third-party library hosts. The harness records those two
categories separately (including total critical transfer) so visible user cost
remains inspectable without turning a viewport-dependent tile count into a
pass/fail target.

Production MapServer uses a generated public-only include and Atlas registry;
both omit development-only drought layers. After any production deployment,
run `python3 tools/check_public_wms_layers.py --url https://lab.tigrayinsights.net/map/ogc`
to make every advertised WMS layer return a PNG before declaring the release
healthy.

## Running it

```bash
pip install playwright && playwright install chromium

python3 tools/measure_public_performance.py --dry-run          # validate config only
python3 tools/measure_public_performance.py --page drought     # measure, print table
python3 tools/measure_public_performance.py --check --archive  # gate a change and keep the run
```

`--check` exits non-zero when an enforced budget fails or cannot be measured.
`--runs N` takes the median of N cold loads, which is worth doing before
declaring a stage complete. Every archived run records the date, commit, browser
version, viewport, network profile, cache state and the ten largest responses,
so a regression can be attributed rather than argued about.

## Reading the first run

Two things will look wrong on the first run, and both are expected.

1. The functional check will report that its selectors are unverified. The
   click target and success text in the budget file were written from
   observation of the live page, not from a passing run. Confirm them once and
   set `selectors_verified_on_production` to true.
2. The functional check cannot pass at all until the Tabia detail panel stops
   calling the database-backed boundary route and falls back to packaged release
   geometry. Until then the harness records a failure with that reason, which is
   the honest state of the public product rather than a harness defect.

## Scope

The harness issues ordinary GET requests to public pages as a browser would. It
does not authenticate, write, publish, or touch development services, n8n,
Docker, the database or the VPS.
