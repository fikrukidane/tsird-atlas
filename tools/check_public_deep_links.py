#!/usr/bin/env python3
"""Certify Stage 2 map/table deep links against a public-compatible stage.

The checker deliberately needs only two retained snapshots: one CHIRPS
observed-rainfall run and one NDVI run.  The remaining cases use an invented
missing run and a stale release string, so this does not turn the stage into a
copy of the full evidence archive.
"""
from __future__ import annotations

import argparse
import datetime as dt
from importlib.metadata import version as package_version
import json
from pathlib import Path
import sys
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs" / "ui" / "baseline"
HARNESS_VERSION = "tsird-public-deep-link-check/v1"


def api_json(page, url: str) -> dict:
    response = page.request.get(url)
    if not response.ok:
        raise RuntimeError(f"fixture request failed ({response.status}): {url}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"fixture response was not an object: {url}")
    return payload


def retained_run(index: dict) -> str:
    runs = index.get("runs")
    if not isinstance(runs, list) or len(runs) < 2 or not isinstance(runs[1], dict):
        raise RuntimeError("stage does not expose a historical retained run")
    run_id = runs[1].get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError("historical retained run has no run_id")
    return run_id


def wait_workspace(page) -> None:
    page.wait_for_function(
        """() => document.body.dataset.tsirdDroughtGeometry === 'ready'""",
        timeout=15000,
    )


def check_case(page, name: str, url: str, assertion) -> dict:
    errors: list[str] = []
    listener = lambda error: errors.append(str(error))
    page.on("pageerror", listener)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        assertion(page)
        if errors:
            raise RuntimeError(f"uncaught browser error: {errors[0]}")
        return {"name": name, "url": url, "passed": True}
    except Exception as error:
        return {"name": name, "url": url, "passed": False, "error": str(error)}
    finally:
        page.remove_listener("pageerror", listener)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--archive", action="store_true")
    parser.add_argument("--label", default="")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is required: pip install playwright && playwright install chromium", file=sys.stderr)
        return 2

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        toolchain = {
            "harness_version": HARNESS_VERSION,
            "playwright_version": package_version("playwright"),
            "chromium_version": browser.version,
        }
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.set_default_timeout(15000)
        observed_run = retained_run(api_json(page, f"{base}/map/api/drought/public/dashboard/observed-rainfall/runs"))
        ndvi_run = retained_run(api_json(page, f"{base}/map/api/drought/public/dashboard/evidence/ndvi/runs"))
        observed = api_json(page, f"{base}/map/api/drought/public/dashboard/observed-rainfall/runs/{observed_run}")
        conditions = observed.get("conditions")
        if not isinstance(conditions, list) or not conditions or not isinstance(conditions[0], dict):
            raise RuntimeError("historical observed fixture has no Tabia rows")
        tabia_id = conditions[0].get("tsird_tabia_id")
        if not isinstance(tabia_id, str) or not tabia_id:
            raise RuntimeError("historical observed fixture has no Tabia ID")
        overview = api_json(page, f"{base}/map/api/drought/public/dashboard/overview")
        release_id = ((overview.get("indicator_release") or {}).get("release_id"))
        if not isinstance(release_id, str) or not release_id:
            raise RuntimeError("stage overview has no active indicator release ID")

        common = {"tabia": tabia_id, "release": release_id}
        observed_query = urlencode({**common, "indicator": "rainfall", "month": observed_run})
        ndvi_query = urlencode({**common, "indicator": "vegetation", "month": ndvi_run})
        missing_query = urlencode({**common, "indicator": "rainfall", "month": "not-a-retained-run"})
        stale_query = urlencode({**common, "indicator": "rainfall", "month": observed_run, "release": "superseded-fixture"})

        def expect_select(active, selector: str, value: str) -> None:
            control = active.locator(selector)
            control.wait_for()
            actual = control.input_value()
            if actual != value:
                raise RuntimeError(f"{selector} restored {actual!r}, expected {value!r}")

        def expect_selected_tabia(active) -> None:
            active.locator(f'[data-selected-tabia="{tabia_id}"]').wait_for()

        def observed_restore(active) -> None:
            wait_workspace(active)
            expect_select(active, "select[data-observed-snapshot]", observed_run)
            expect_selected_tabia(active)

        def ndvi_restore(active) -> None:
            wait_workspace(active)
            expect_select(active, "select[data-indicator-snapshot]", ndvi_run)
            expect_selected_tabia(active)

        def unknown_run(active) -> None:
            wait_workspace(active)
            expect_select(active, "select[data-observed-snapshot]", "latest")

        def stale_release(active) -> None:
            wait_workspace(active)
            active.locator(".drought-release-notice").wait_for()

        def table_shared_parameters(active) -> None:
            active.locator("tr[aria-current='true']").wait_for()
            if observed_run not in active.locator("#drought-table-release").inner_text():
                raise RuntimeError("table did not preserve the historical month")
            if observed_run not in (active.locator("#map-view-link").get_attribute("href") or ""):
                raise RuntimeError("table map link lost shared parameters")

        cases = [
            ("observed historical restore", f"{base}/map/drought/?{observed_query}", observed_restore),
            ("NDVI historical restore", f"{base}/map/drought/?{ndvi_query}", ndvi_restore),
            ("unknown run falls back", f"{base}/map/drought/?{missing_query}", unknown_run),
            ("stale release is explicit", f"{base}/map/drought/?{stale_query}", stale_release),
            ("table shares historical parameters", f"{base}/map/drought/table/?{observed_query}", table_shared_parameters),
        ]
        results = []
        for name, url, assertion in cases:
            result = check_case(page, name, url, assertion)
            results.append(result)
            print(f"{result['name']}: {'PASS' if result['passed'] else result['error']}")
        browser.close()

    if args.archive:
        label = "".join(char if char.isalnum() or char == "-" else "-" for char in args.label.lower()).strip("-")
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = f"-{label}" if label else ""
        path = ARCHIVE / f"{stamp}-stage-2-deep-links{suffix}.json"
        path.write_text(json.dumps({"base_url": base, "label": label or None, "toolchain": toolchain, "fixtures": {"observed_run": observed_run, "ndvi_run": ndvi_run, "tabia_id": tabia_id}, "results": results}, indent=2) + "\n", encoding="utf-8")
        print(f"archived {path.relative_to(ROOT)}")
    failed = any(not result["passed"] for result in results)
    return 1 if args.check and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
