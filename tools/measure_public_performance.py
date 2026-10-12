#!/usr/bin/env python3
"""Measure the published TSIRD pages against a committed performance budget.

The harness drives a real browser through Playwright, applies a fixed network
and CPU profile, and records transfer bytes from Chrome DevTools Protocol
accounting rather than from estimates.  It measures a cold visit and a repeat
visit separately, and it times the functional check that matters for the
drought workspace: selecting a Tabia and reading back its indicator values.

It never writes to the site.  Every request it makes is a GET issued by the
browser while loading public pages.

Install once:

    pip install playwright && playwright install chromium

Usage:

    python3 tools/measure_public_performance.py --dry-run
    python3 tools/measure_public_performance.py --page drought
    python3 tools/measure_public_performance.py --check --archive

Exit code is 1 when --check is given and an enforced budget is exceeded.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import pathlib
import statistics
import subprocess
import sys
from urllib.parse import urlparse

HARNESS_VERSION = "1.2.0"
ROOT = pathlib.Path(__file__).resolve().parents[1]
BUDGET_FILE = ROOT / "tools" / "performance-budget.json"
ARCHIVE_DIR = ROOT / "docs" / "performance" / "baseline"


def load_budget(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_commit() -> str:
    supplied = os.environ.get("TSIRD_GIT_COMMIT", "").strip()
    if supplied:
        return supplied
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class Accounting:
    """Collect per-response transfer bytes and completion times over CDP."""

    def __init__(self, cdp, classification: dict):
        self.cdp = cdp
        self.basemap = set(classification.get("basemap_hosts", []))
        self.third_party = set(classification.get("third_party_hosts", []))
        self.requests: dict[str, dict] = {}
        self.finished: list[dict] = []
        cdp.on("Network.requestWillBeSent", self._sent)
        cdp.on("Network.responseReceived", self._received)
        cdp.on("Network.loadingFinished", self._done)

    def _sent(self, event):
        self.requests.setdefault(event["requestId"], {})["url"] = event["request"]["url"]

    def _received(self, event):
        entry = self.requests.setdefault(event["requestId"], {})
        entry["url"] = event["response"]["url"]
        entry["status"] = event["response"].get("status")
        entry["mime"] = event["response"].get("mimeType")

    def _done(self, event):
        entry = self.requests.get(event["requestId"], {})
        url = entry.get("url", "")
        if not url:
            return
        host = urlparse(url).hostname or ""
        self.finished.append({
            "url": url,
            "host": host,
            "status": entry.get("status"),
            "mime": entry.get("mime"),
            "bytes": int(event.get("encodedDataLength") or 0),
            "ts": float(event.get("timestamp") or 0.0),
            "kind": ("basemap" if host in self.basemap
                     else "third_party" if host in self.third_party
                     else "application"),
        })

    def summary(self, cutoff_ts: float | None = None) -> dict:
        rows = self.finished
        app = [r for r in rows if r["kind"] == "application"]
        basemap = [r for r in rows if r["kind"] == "basemap"]
        third = [r for r in rows if r["kind"] == "third_party"]
        critical = [r for r in rows if cutoff_ts is None or r["ts"] <= cutoff_ts]
        critical_app = [r for r in critical if r["kind"] == "application"]
        biggest = sorted(rows, key=lambda r: r["bytes"], reverse=True)[:10]
        return {
            "total_kb": round(sum(r["bytes"] for r in rows) / 1024, 1),
            "application_kb": round(sum(r["bytes"] for r in app) / 1024, 1),
            "third_party_kb": round(sum(r["bytes"] for r in third) / 1024, 1),
            "basemap_kb": round(sum(r["bytes"] for r in basemap) / 1024, 1),
            "critical_path_kb": round(sum(r["bytes"] for r in critical_app) / 1024, 1),
            "critical_total_kb": round(sum(r["bytes"] for r in critical) / 1024, 1),
            "requests": len(rows),
            "app_requests": len(app),
            "basemap_tile_requests": len(basemap),
            "largest_responses": [
                {"kb": round(r["bytes"] / 1024, 1), "status": r["status"],
                 "url": r["url"].split("?")[0][-90:]} for r in biggest
            ],
        }


def apply_profile(cdp, profile: dict) -> None:
    down = profile["download_kbps"] * 1024 / 8
    up = profile["upload_kbps"] * 1024 / 8
    cdp.send("Network.emulateNetworkConditions", {
        "offline": False,
        "latency": profile["latency_ms"],
        "downloadThroughput": down if down else -1,
        "uploadThroughput": up if up else -1,
    })
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": profile.get("cpu_slowdown", 1)})


def cdp_timestamp(cdp) -> float | None:
    """Read the CDP monotonic timestamp at an interaction boundary."""
    try:
        metrics = cdp.send("Performance.getMetrics").get("metrics", [])
        value = next((item.get("value") for item in metrics if item.get("name") == "Timestamp"), None)
        return float(value) if value is not None else None
    except Exception:  # pragma: no cover - browser-version dependent
        return None


def install_restored_selection_probe(page) -> None:
    """Record a deep-link selection at the moment the page creates it.

    The script is installed before navigation.  It intercepts the dashboard's
    paint-aware selection mark, rather than looking for the card only after
    the dashboard reports itself ready; the latter can make a completed restore
    appear to take zero seconds.
    """
    page.add_init_script("""() => {
      const key = '__tsirdRestoredSelectionAt';
      const markName = 'tsird-public-restored-selection-observed';
      const appMarkName = 'tsird-public-evidence-selection-ready';
      let observer;
      let timer;
      try {
        const originalMark = performance.mark.bind(performance);
        performance.mark = (name, ...args) => {
          const result = originalMark(name, ...args);
          if (name === appMarkName && !Number.isFinite(window[key])) {
            window[key] = performance.getEntriesByName(name).at(-1)?.startTime ?? performance.now();
            performance.mark(markName);
          }
          return result;
        };
      } catch (_) {
        // The DOM probe below remains a fallback for browsers that do not
        // allow a Performance method override.
      }
      const record = () => {
        if (Number.isFinite(window[key])) return;
        const card = document.querySelector('[data-selected-tabia]');
        const panel = document.getElementById('drought-dashboard');
        if (!card || !panel || panel.classList.contains('is-hidden') ||
            getComputedStyle(panel).display === 'none') return;
        window[key] = performance.now();
        performance.mark(markName);
        if (observer) observer.disconnect();
        if (timer) clearInterval(timer);
      };
      observer = new MutationObserver(record);
      observer.observe(document, {
        subtree: true,
        childList: true,
        attributes: true,
        attributeFilter: ['data-selected-tabia', 'class'],
      });
      document.addEventListener('DOMContentLoaded', record, { once: true });
      // Some dashboard updates prepare an element while it is detached, then
      // attach it without mutating the selected attribute in the observed
      // tree.  The short poll remains pre-navigation instrumentation and
      // closes that ordering gap without depending on harness polling.
      timer = setInterval(record, 10);
    }""")


def run_visit(page, cdp, acct, url: str, spec: dict, cache_state: str) -> dict:
    """Load one page and, when configured, time the functional check."""
    started = page.evaluate("() => performance.timeOrigin + performance.now()") if cache_state == "repeat" else None
    page.goto(url, wait_until="commit", timeout=120000)
    # CDP network completion timestamps use a monotonic clock, whereas the
    # page records its selection with performance.now().  An anchor in the
    # newly committed document maps the pre-armed selection event into CDP's
    # clock without delaying the cutoff until the harness polls it.
    clock_anchor_browser = page.evaluate("() => performance.now()")
    clock_anchor_cdp = cdp_timestamp(cdp)
    ready = spec.get("ready_signal") or {}
    if ready.get("text"):
        try:
            page.get_by_text(ready["text"], exact=False).first.wait_for(
                timeout=ready.get("timeout_ms", 60000))
        except Exception:
            pass
    functional = {"attempted": False, "succeeded": False, "seconds": None, "note": None}
    check = spec.get("functional_check")
    if check and check.get("click", {}).get("strategy") == "restored_public_selection":
        functional["attempted"] = True
        try:
            success_selector = check.get("success_selector")
            page.wait_for_function(
                """selector => {
                  const card = document.querySelector(selector);
                  const panel = document.getElementById('drought-dashboard');
                  const observedAt = window.__tsirdRestoredSelectionAt;
                  return Boolean(card && panel && Number.isFinite(observedAt) &&
                    !panel.classList.contains('is-hidden') &&
                    getComputedStyle(panel).display !== 'none');
                }""",
                arg=success_selector,
                timeout=check.get("timeout_ms", 30000),
                polling=50,
            )
            mark = page.evaluate("() => window.__tsirdRestoredSelectionAt ?? null")
            if mark is None:
                raise RuntimeError("pre-navigation restored-selection probe did not fire")
            functional.update(
                succeeded=True,
                seconds=round(mark / 1000, 3),
                timing_origin="navigation-start",
                note=f"restored selection matched {success_selector!r} via pre-navigation probe",
            )
            if clock_anchor_cdp is not None:
                functional["completion_cdp_timestamp"] = round(
                    clock_anchor_cdp + (mark - clock_anchor_browser) / 1000, 6)
        except Exception as exc:  # pragma: no cover - environment dependent
            functional["note"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        check = None
    if check:
        functional["attempted"] = True
        try:
            ready_selector = check.get("ready_selector")
            if ready_selector:
                page.locator(ready_selector).wait_for(timeout=check.get("timeout_ms", 30000))
            before_click_selector = check.get("before_click_selector")
            if before_click_selector:
                page.locator(before_click_selector).click(timeout=check.get("timeout_ms", 30000))
            click = check.get("click", {})
            if click.get("strategy") == "first_public_evidence_feature":
                point = page.evaluate("""() => {
                  const map = window.TSIRD_PUBLIC_DROUGHT_MAP;
                  if (!map || !map.getSize()) throw new Error('public drought map test hook unavailable');
                  const [width, height] = map.getSize();
                  const target = map.getTargetElement();
                  const rect = target.getBoundingClientRect();
                  for (let y = 6; y < height - 6; y += 10) {
                    for (let x = 6; x < width - 6; x += 10) {
                      // On narrow screens the dashboard can cover much of the
                      // map. Only choose a rendered feature at a point that is
                      // actually exposed to the user, rather than one hidden
                      // under the panel.
                      const top = document.elementFromPoint(rect.left + x, rect.top + y);
                      if (!top || !target.contains(top)) continue;
                      const feature = map.forEachFeatureAtPixel([x, y], candidate =>
                        candidate && candidate.get && candidate.get('tsird_tabia_id') ? candidate : null);
                      if (feature) {
                        return {x, y};
                      }
                    }
                  }
                  throw new Error('no rendered public Tabia feature found');
                }""")
            else:
                box = page.locator("canvas").first.bounding_box(timeout=30000)
                point = {
                    "x": box["x"] + box["width"] / 2 + click.get("dx", 0),
                    "y": box["y"] + box["height"] / 2 + click.get("dy", 0),
                }
            # This is an interaction budget: measure from the user's map click,
            # not from navigation start. Page delivery is measured separately by
            # the transfer and paint metrics below.
            t0 = page.evaluate("() => performance.now()")
            if click.get("strategy") == "first_public_evidence_feature":
                # The feature scan uses map-local pixels. Translate them to
                # viewport coordinates and inject a real mouse event, avoiding
                # Playwright locator-stability waits from contaminating the
                # user-visible post-click response time.
                map_box = page.locator("#map").bounding_box(timeout=30000)
                page.mouse.click(map_box["x"] + point["x"], map_box["y"] + point["y"])
            else:
                page.mouse.click(point["x"], point["y"])
            deadline = check.get("timeout_ms", 30000)
            found = None
            success_selector = check.get("success_selector")
            if success_selector:
                try:
                    # A dashboard reflow can keep Playwright's locator
                    # "visible" heuristic waiting after the selected card has
                    # been inserted and displayed. The functional condition is
                    # the real contract: selected evidence exists and its
                    # containing panel is not hidden.
                    page.wait_for_function(
                        """selector => {
                          const card = document.querySelector(selector);
                          const panel = document.getElementById('drought-dashboard');
                          const painted = performance.getEntriesByName('tsird-public-evidence-selection-ready').length > 0;
                          return Boolean(card && panel && painted && !panel.classList.contains('is-hidden') && getComputedStyle(panel).display !== 'none');
                        }""",
                        arg=success_selector,
                        timeout=deadline,
                        polling=50,
                    )
                    found = success_selector
                    functional["handler_seconds"] = round(
                        (page.evaluate("() => performance.getEntriesByName('tsird-public-evidence-selection-ready').at(-1)?.startTime || null") - t0) / 1000,
                        3,
                    )
                    functional["seconds"] = functional["handler_seconds"]
                except Exception as error:
                    # Preserve the selector diagnostic in the archived run;
                    # otherwise a failed interaction is indistinguishable from
                    # a page that merely lacks the expected card.
                    functional["selector_error"] = f"{type(error).__name__}: {str(error)[:240]}"
            if not found and not success_selector:
                for text in check.get("success_text_any", []):
                    try:
                        page.get_by_text(text, exact=False).first.wait_for(timeout=deadline // max(1, len(check["success_text_any"])))
                        found = text
                        break
                    except Exception:
                        continue
            now = page.evaluate("() => performance.now()")
            if found:
                functional.update(
                    succeeded=True,
                    seconds=functional.get("handler_seconds", round((now - t0) / 1000, 2)),
                    note=f"matched {found!r}",
                )
            else:
                body = page.inner_text("body")[:4000]
                known = [t for t in check.get("known_failure_text_any", []) if t in body]
                functional["note"] = (f"no success text; page shows {known[0]!r}" if known
                                      else "no success text matched; selectors need verification")
        except Exception as exc:  # pragma: no cover - environment dependent
            functional["note"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    cutoff = None
    if functional.get("succeeded"):
        cutoff = functional.get("completion_cdp_timestamp") or cdp_timestamp(cdp)
    paint = page.evaluate(
        "() => { const p = performance.getEntriesByType('paint')"
        ".find(e => e.name === 'first-contentful-paint'); return p ? Math.round(p.startTime) : null; }")
    nav = page.evaluate(
        "() => { const n = performance.getEntriesByType('navigation')[0];"
        " return n ? {ttfb: Math.round(n.responseStart), load: Math.round(n.loadEventEnd)} : null; }")
    result = acct.summary(cutoff)
    result.update({"cache_state": cache_state, "first_contentful_paint_ms": paint,
                   "navigation": nav, "functional_check": functional,
                   "critical_path_cutoff": (
                       "restored-selection-event" if functional.get("completion_cdp_timestamp")
                       else "functional-success" if cutoff else "whole-load")})
    if started:
        result["note"] = "repeat visit in the same browser context"
    return result


def measure(budget: dict, page_key: str, profile_name: str, viewport_name: str,
            base_url: str, path_override: str | None = None, restored_selection: bool = False) -> dict:
    from playwright.sync_api import sync_playwright

    spec = copy.deepcopy(budget["pages"][page_key])
    if restored_selection:
        spec["functional_check"] = {
            "description": "Restore the Tabia evidence selection carried by the deep link.",
            "ready_selector": "body[data-tsird-drought-geometry='ready']",
            "click": {"strategy": "restored_public_selection"},
            "success_selector": "[data-selected-tabia]",
            "timeout_ms": 30000,
        }
    profile = budget["network_profiles"][profile_name]
    viewport = budget["viewports"][viewport_name]
    path = path_override or spec["path"]
    if not path.startswith("/"):
        raise ValueError("--path must begin with /")
    url = base_url.rstrip("/") + path
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport={"width": viewport["width"], "height": viewport["height"]},
            device_scale_factor=viewport.get("device_scale_factor", 1))
        page = context.new_page()
        if restored_selection:
            install_restored_selection_probe(page)
        cdp = context.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send("Performance.enable")
        apply_profile(cdp, profile)
        cold_acct = Accounting(cdp, budget.get("classification", {}))
        cold = run_visit(page, cdp, cold_acct, url, spec, "cold")
        repeat_acct = Accounting(cdp, budget.get("classification", {}))
        repeat = run_visit(page, cdp, repeat_acct, url, spec, "repeat")
        browser_version = browser.version
        browser.close()
    return {
        "page": page_key, "path": path, "url": url,
        "environment": {
            "measured_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "harness_version": HARNESS_VERSION, "git_commit": git_commit(),
            "browser": browser_version, "viewport": viewport_name, "viewport_px": viewport,
            "network_profile": profile_name, "network_profile_values": profile,
            "method": "playwright + cdp network accounting",
        },
        "cold": cold, "repeat": repeat,
    }


def evaluate(budget: dict, result: dict) -> list[dict]:
    spec = budget["pages"][result["page"]]
    cold, repeat = result["cold"], result["repeat"]
    observed = {
        "critical_path_kb": cold["critical_path_kb"],
        "critical_total_kb": cold["critical_total_kb"],
        "total_cold_kb": cold["application_kb"],
        "app_requests": cold["app_requests"],
        "functional_seconds": (cold.get("functional_check") or {}).get("seconds"),
        "basemap_tile_requests": cold["basemap_tile_requests"],
        "repeat_total_kb": repeat["application_kb"],
        "repeat_functional_seconds": (repeat.get("functional_check") or {}).get("seconds"),
    }
    rows = []
    for name, rule in spec["budgets"].items():
        value = observed.get(name)
        target, mode = rule.get("target"), rule.get("mode", "record")
        if mode != "enforce" or target is None:
            verdict = "record"
        elif value is None:
            verdict = "NOT MEASURED"
        else:
            verdict = "pass" if value <= target else "FAIL"
        rows.append({"measure": name, "observed": value, "target": target,
                     "mode": mode, "verdict": verdict})
    return rows


def print_table(result: dict, rows: list[dict]) -> None:
    env = result["environment"]
    print(f"\n{result['page']}  {result['url']}")
    print(f"  {env['measured_at']}  profile={env['network_profile']} "
          f"viewport={env['viewport']} commit={env['git_commit']}")
    print(f"  {'measure':<28}{'observed':>12}{'target':>10}   verdict")
    for row in rows:
        obs = "n/a" if row["observed"] is None else f"{row['observed']}"
        tgt = "-" if row["target"] is None else f"{row['target']}"
        print(f"  {row['measure']:<28}{obs:>12}{tgt:>10}   {row['verdict']}")
    fc = result["cold"].get("functional_check") or {}
    if fc.get("attempted") and not fc.get("succeeded"):
        print(f"  functional check did not complete: {fc.get('note')}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--budget", default=str(BUDGET_FILE))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--page", default="all")
    parser.add_argument("--path", default=None, help="override one page path, including a deep-link query string")
    parser.add_argument("--restored-selection", action="store_true", help="measure deep-link restoration instead of injecting a map click")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--viewport", default=None)
    parser.add_argument("--runs", type=int, default=1, help="median of N cold runs")
    parser.add_argument("--archive", action="store_true", help="write results under docs/performance/baseline/")
    parser.add_argument("--label", default="", help="optional safe label added to an archived result filename")
    parser.add_argument("--check", action="store_true", help="exit 1 when an enforced budget fails")
    parser.add_argument("--dry-run", action="store_true", help="validate configuration without a browser")
    args = parser.parse_args(argv[1:])

    budget = load_budget(pathlib.Path(args.budget))
    base_url = args.base_url or budget["base_url"]
    profile = args.profile or budget["default_profile"]
    viewport = args.viewport or budget["default_viewport"]
    pages = list(budget["pages"]) if args.page == "all" else [args.page]
    if (args.path or args.restored_selection) and len(pages) != 1:
        print("--path and --restored-selection require exactly one --page")
        return 2
    if args.restored_selection and not args.path:
        print("--restored-selection requires --path")
        return 2
    for key in pages:
        if key not in budget["pages"]:
            print(f"unknown page {key!r}; known: {list(budget['pages'])}")
            return 2
    if profile not in budget["network_profiles"] or viewport not in budget["viewports"]:
        print("unknown profile or viewport")
        return 2

    if args.dry_run:
        print(f"budget {budget['schema_version']} stage={budget['stage']}")
        print(f"base_url={base_url} profile={profile} viewport={viewport} pages={pages}")
        for key in pages:
            spec = budget["pages"][key]
            enforced = [n for n, r in spec["budgets"].items() if r.get("mode") == "enforce"]
            check = spec.get("functional_check")
            print(f"  {key}: {spec['path']} enforced={enforced} "
                  f"functional_check={'yes' if check else 'no'}"
                  + ("" if not check else
                     f" selectors_verified={check.get('selectors_verified_on_production')}"))
        print("dry run only; no browser was started")
        return 0

    failures = 0
    for key in pages:
        runs = [measure(budget, key, profile, viewport, base_url, args.path, args.restored_selection) for _ in range(max(1, args.runs))]
        result = runs[0]
        if len(runs) > 1:
            for field in ("total_kb", "application_kb", "critical_path_kb", "app_requests"):
                result["cold"][field] = statistics.median(r["cold"][field] for r in runs)
            secs = [(r["cold"].get("functional_check") or {}).get("seconds") for r in runs]
            secs = [s for s in secs if s is not None]
            if secs:
                result["cold"]["functional_check"]["seconds"] = statistics.median(secs)
            result["environment"]["runs"] = len(runs)
        rows = evaluate(budget, result)
        result["verdicts"] = rows
        print_table(result, rows)
        failures += sum(1 for row in rows if row["verdict"] in {"FAIL", "NOT MEASURED"})
        if args.archive:
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            stamp = result["environment"]["measured_at"].replace(":", "").replace("-", "")
            label = ""
            if args.label:
                cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in args.label).strip("-_")
                if not cleaned:
                    print("archive label must contain a letter, number, hyphen or underscore")
                    return 2
                label = f"-{cleaned}"
            out = ARCHIVE_DIR / f"{stamp}-{key}-{profile}-{viewport}{label}.json"
            out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(f"  archived {out.relative_to(ROOT)}")
    if args.check and failures:
        print(f"\n{failures} enforced budget(s) failed or unmeasured")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
