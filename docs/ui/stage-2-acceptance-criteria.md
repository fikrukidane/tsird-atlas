# Public workspace Stage 2 acceptance criteria

Status: **acceptance gate, written before implementation.** Nothing in this
document changes the site. It defines what "Stage 2 passed" means, so that the
work can be accepted or rejected on measurement rather than on impression.

Stage 1 was a byte budget, which is easy to judge objectively. Stage 2 is
usability, which is not. That is the reason for writing the criteria first and
for expressing each one as something a harness can read out of the DOM.

Stage 1's criteria remain in force: see
[`docs/performance/README.md`](../performance/README.md). Stage 2 must not
regress them.

## Scope

Three deliverables, in this implementation order:

- **A. Mobile layout.** The largest remaining defect, and the audience is
  phone-first.
- **B. Deep links.** Indicator, month and Tabia encoded in the URL.
- **C. Accessibility and a table view.** Keyboard access, announced selection,
  colour-safe encoding, and a plain table that doubles as the low-bandwidth
  fallback.

Each lands as its own pull request with its own measured run, as in Stage 1.

Out of scope, deliberately deferred: OpenLayers upgrade, a bundler, MapLibre,
cloud-optimised rasters, a self-hosted basemap. Those were postponed because
usability precedes architecture, and nothing here changes that order.

## Measured baseline, 12 October 2026

Production commit `84481c8`, indicator release
`2026-10-12T045350Z-indicators`, page `/map/drought/`, emulated at a 390 px
layout viewport, measured in-browser with `getBoundingClientRect()`.

| Observation | Measured |
| --- | --- |
| Horizontal overflow | `document.documentElement.scrollWidth` is 776 px against a 390 px client width: **386 px of overflow** |
| Cause of the overflow | `.site-nav` is one non-wrapping row 639 px wide, beginning at x=137 and ending at x=777 |
| Page title | `header h1` is 107 px tall at a 20 px font: **four wrapped lines** |
| Header cost | 131 px of vertical space before any map is visible |
| Dashboard panel | `#drought-dashboard` is `position: absolute`, 362 px wide and 685 px tall, inset 20 px from the left of a 390 px map: roughly 28 px of map width remains uncovered |
| Touch targets | **21** interactive elements fall below 44 px in their smaller dimension: nav links 32 px tall, map zoom buttons 33x33, panel close 24x22, indicator buttons 29 px tall |
| Existing breakpoints | four thresholds in four files (900 px in `public-workspace.css`, 760 px in `drought-workspace.css`, 700 px in `drought-dashboard.css`, 768 px in `style.css`), none of which prevents the overflow above |

One caveat on method: under viewport emulation `window.innerWidth` did not
agree with `document.documentElement.clientWidth`. Every number above is an
element measurement taken in the same layout pass, so the relationships hold,
but the absolute figures should be re-measured on a real device profile before
they are quoted anywhere outside this document.

## A. Mobile layout

Enforced at **360x740** and **390x844**. **320x568 is measured and recorded
but never blocks a release**: it protects against a regression on the smallest
phones still in use without making Stage 2 chase layouts that are leaving the
field.

Applies to every public route: `/map/drought/`, `/map/drought/table/`,
`/map/drought/release/`, `/map/drought/priority/`,
`/map/drought/priority/model/`, `/map/drought/priority/scenario/`, and `/map/`.
The local-only `/map/drought/control/` page is excluded.

| ID | Criterion | Target | Mode |
| --- | --- | --- | --- |
| A1 | Horizontal overflow | `scrollWidth <= clientWidth + 1` on every route, at both enforced widths | enforce |
| A2 | Map remains usable with the panel open | at least **45 %** of viewport height shows map that the panel does not cover | enforce |
| A3 | Header cost | header height **<= 96 px**; title occupies **<= 2 lines** | enforce |
| A4 | Touch targets | every interactive element is **>= 44x44 CSS px**, or >= 44 px in one dimension with >= 8 px clear spacing | enforce |
| A5 | Panel dismissal | the panel can be collapsed and reopened without a page reload, and its state is readable from the DOM | enforce |
| A6 | Viewport zoom | no `user-scalable=no` and no `maximum-scale` below 5 | enforce |
| A7 | Breakpoint consolidation | the four current thresholds reduced to one documented set | record |
| A8 | Smallest phones | A1 to A6 measured at 320x568 and reported, pass or fail | record |

A2 is the criterion that decides whether the page is usable at all on a phone:
a panel that covers the map turns a map product into a form.

## B. Deep links

| ID | Criterion | Target | Mode |
| --- | --- | --- | --- |
| B1 | Selection updates the URL | choosing an indicator, month or Tabia rewrites the URL without a reload | enforce |
| B2 | Cold restore | opening that URL restores the same indicator, month and Tabia, or states plainly why it cannot | enforce |
| B3 | Stable identity | a Tabia is addressed by `tsird_tabia_id`, never by array index or display name | enforce |
| B4 | Release honesty | a URL carrying a release ID shows that release's values, or says the release is superseded; it never silently shows different numbers under the same link | enforce |
| B5 | Malformed input | unknown or malformed parameters fall back to the default view with no uncaught exception | enforce |
| B6 | Restore cost | a deep-link cold load still meets the Stage 1 functional budget of <= 3 s on `slow-4g` | enforce |
| B7 | Shared parameters | `/map/drought/table/` accepts and emits the same indicator, month, Tabia and release parameters as the map route, and a selection on either route links to the equivalent view on the other | enforce |

B4 is the criterion with evidence consequences. A link pasted into a report or
a message must not change meaning when the next indicator release lands. The
release-ID assets are already immutable, so the honest options are to serve the
pinned release or to say it has been superseded; quietly substituting current
values is not one of them.

## C. Accessibility and table view

| ID | Criterion | Target | Mode |
| --- | --- | --- | --- |
| C1 | Keyboard selection | a Tabia can be reached and selected by keyboard alone, with a visible focus indicator at >= 3:1 contrast | enforce |
| C2 | Announced selection | a `polite` ARIA live region announces the selected Tabia and the current indicator value | enforce |
| C3 | Colour ramp | passes a deuteranopia and protanopia simulation check, with >= 3:1 between adjacent classes | enforce |
| C4 | Insufficient evidence | encoded by pattern or hatch **and** text, never by colour alone | enforce |
| C5 | Text contrast | >= 4.5:1 for body text and >= 3:1 for large text, panel and legend included | enforce |
| C6 | Table view | a separate **`/map/drought/table/`** route listing the current indicator for all 748 Tabias in real table semantics, sortable, with a clearly labelled "Table view" link in the map panel | enforce |
| C7 | Documented fallback | with `body[data-tsird-drought-geometry]` reporting an unavailable boundary, the map route surfaces the table link and the table route still reports values | enforce |
| C8 | Automated audit | zero critical or serious violations from axe-core, or an equivalent, on each public route | enforce |
| C9 | Language marking | the Tigrinya place names already present are correct and carry `lang="ti"`; no interface string is translated in this stage | enforce |
| C10 | Table route independence | `/map/drought/table/` renders its values without loading the map stack: no OpenLayers, no basemap tiles, no `cdn.jsdelivr.net` request | enforce |
| C11 | Table route transfer | its own cold transfer on `slow-4g`, recorded. Expectation on first measurement is well under 250 KB, since it carries values and no geometry; the target is set once measured rather than guessed now | record |

C6, C7, C10 and C11 are one feature with two purposes. The table is the
accessible view, and it is also what the workspace falls back to when geometry
cannot be delivered, which is the failure mode this platform has actually had
in production.

Giving the table its own route rather than another panel mode is what makes
that second purpose real. A panel mode inherits the whole map stack, so it
fails in exactly the conditions it is meant to survive: a slow connection, a
missing boundary asset, a screen reader on a page whose primary control is a
canvas. A separate route can be opened, linked and read on its own, which is
why C10 forbids it from pulling the map stack back in through the side door.

## What Stage 2 must not do

- **Must not regress Stage 1.** Critical path <= 400 KB, critical total
  <= 650 KB, total cold <= 1.5 MB, <= 15 application requests, functional check
  <= 3 s. Table markup and ARIA structure add bytes; if the table cannot fit
  inside the budget it loads on demand, and that demand load is recorded.
- **Must not change evidence.** Display and interaction only. The PostGIS
  boundaries behind the zonal statistics, and every published indicator value,
  stay exactly as they are.
- **Must not add a third-party host.** The current third-party set is
  `cdn.jsdelivr.net` alone.
- **Must not introduce a build step or a framework.** Classic scripts stay
  classic scripts for this stage.

## How it is checked

- `tools/usability-criteria.json`, committed alongside
  `tools/performance-budget.json`, holds the thresholds above as data so that a
  change to a target is a reviewable diff rather than a reinterpretation of
  prose. It reuses the existing `viewports` and `network_profiles` definitions
  instead of restating them.
- `tools/check_public_usability.py` drives the same Playwright and CDP setup as
  `tools/measure_public_performance.py`, reads the criteria file, and exits 1
  when an enforced criterion fails.
- Runs are archived to `docs/ui/baseline/<timestamp>-<page>-<viewport>.json`,
  mirroring the performance baseline convention.
- The Stage 1 performance harness is re-run on the final Stage 2 build, and its
  archived run is cited in the acceptance report.

A criterion that the harness cannot read out of the DOM is recorded as a manual
check with a named observation, not silently dropped.

### Two-step release acceptance

A successful isolated-stage run certifies the candidate implementation only;
it is **not** a statement about the public site. Every archived run records the
harness, Playwright and Chromium versions so a later rerun remains comparable.

Stage 2 is accepted only after both steps below pass and their JSON records are
committed with the release evidence:

1. **Staging certification:** run the usability gate and the Stage 1
   performance gate against the isolated candidate stack, with archives labelled
   `stage2`. The stage carries the two retained historical fixtures required to
   exercise month-pinned links.
2. **Production certification:** after deployment, rerun both gates against
   `https://lab.tigrayinsights.net`, with archives labelled `production`. This
   run must include a month-pinned deep link as well as the bare workspace, so
   B2 and B6 are measured on the real public route rather than inferred from
   staging.

No staging result may be presented as a production measurement, and a release
without the second record remains staging-certified only.

## Decisions, 12 October 2026

The three questions left open when this document was drafted are now settled.
They are recorded here because they change what the criteria above mean.

1. **Enforced widths: 360 px and 390 px. 320 px is recorded, not blocking.**
   Reflected in section A and in A8.
2. **The table is its own route, `/map/drought/table/`**, carrying the same
   indicator, month, Tabia and release parameters, and linked from the map
   panel. Reflected in B7, C6, C7, C10 and C11. The reason for the separate
   route, rather than a panel mode, is in the note under section C.
3. **Tigrinya: place names only in this stage.** The bilingual place names
   already in the data must be correct and correctly marked, and no interface
   string is translated. Full interface localisation is deferred to its own
   phase with reviewed terminology, because a partial and unreviewed
   translation of an evidence product reads as less trustworthy than a clean
   English interface. Reflected in C9.

With these recorded, this document is the acceptance contract for Stage 2.
Changing a target from here on is a reviewable change to this file, not a
reinterpretation during implementation.
