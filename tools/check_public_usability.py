#!/usr/bin/env python3
"""Check the Stage 2 public usability contract with Playwright.

This is a read-only browser check. It records each measured route/viewport in
docs/ui/baseline and exits non-zero only for enforced violations.
"""
from __future__ import annotations

import argparse
import datetime as dt
from importlib.metadata import version as package_version
import json
import pathlib
import re
import sys
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
CRITERIA = ROOT / "tools" / "usability-criteria.json"
ARCHIVE = ROOT / "docs" / "ui" / "baseline"
HARNESS_VERSION = "tsird-public-usability-check/v1"


def measure(page, url: str, width: int, height: int, criteria: dict) -> dict:
    requests: list[str] = []
    def on_request(request):
        requests.append(request.url)

    page.on("request", on_request)
    page.set_viewport_size({"width": width, "height": height})
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        # The dashboard is usable only after its display geometry has reached a
        # terminal state.  `networkidle` can hide a failed or slow geometry
        # request, which is exactly the regression this gate exists to catch.
        if urlparse(url).path.rstrip("/") == "/map/drought":
            page.wait_for_function(
                """() => ['ready', 'unavailable'].includes(document.body.dataset.tsirdDroughtGeometry)""",
                timeout=120000,
            )
        page.wait_for_timeout(250)
        metrics = page.evaluate("""() => {
      const header = document.querySelector('header');
      const title = header && header.querySelector('h1');
      const map = document.getElementById('map');
      const panel = document.getElementById('drought-dashboard');
      const viewport = { width: document.documentElement.clientWidth, height: window.innerHeight };
      const panelRect = panel && !panel.classList.contains('is-hidden') ? panel.getBoundingClientRect() : null;
      const mapRect = map ? map.getBoundingClientRect() : null;
      const mapHeight = mapRect ? Math.max(0, Math.min(viewport.height, mapRect.bottom) - Math.max(0, mapRect.top)) : 0;
      const panelOverlap = panelRect && mapRect ? Math.max(0, Math.min(mapRect.bottom, panelRect.bottom, viewport.height) - Math.max(mapRect.top, panelRect.top, 0)) : 0;
      const actionable = [...document.querySelectorAll('button, a[href], input, select, textarea, [role="button"]')]
        .filter(el => { const s = getComputedStyle(el), r = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && r.width && r.height; })
        .map(el => { const r = el.getBoundingClientRect(); return { tag: el.tagName, text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 80), left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height }; });
      const clearSpacing = item => actionable.every(other => {
        if (other === item) return true;
        const horizontalGap = Math.max(other.left - item.right, item.left - other.right, 0);
        const verticalGap = Math.max(other.top - item.bottom, item.top - other.bottom, 0);
        // A control can use the one-axis exception only when another target
        // does not crowd it on its short axis. A wide but short control still
        // needs vertical clearance; horizontal offset alone is not enough.
        const shortAxis = item.height < 44 ? 'vertical' : 'horizontal';
        return shortAxis === 'vertical' ? verticalGap >= 8 : horizontalGap >= 8;
      });
      const undersized = actionable.filter(item => {
        if (item.width >= 44 && item.height >= 44) return false;
        return !(item.width >= 44 || item.height >= 44) || !clearSpacing(item);
      });
      const titleStyle = title ? getComputedStyle(title) : null;
      const titleLineHeight = titleStyle ? Number.parseFloat(titleStyle.lineHeight) || Number.parseFloat(titleStyle.fontSize) * 1.2 : null;
      const viewportMeta = document.querySelector('meta[name="viewport"]');
      return { scroll_width: document.documentElement.scrollWidth, client_width: document.documentElement.clientWidth,
        header_height: header ? header.getBoundingClientRect().height : 0,
        title_lines: title && titleLineHeight ? Math.ceil(title.getBoundingClientRect().height / titleLineHeight) : null,
        panel_present: Boolean(panelRect),
        map_present: Boolean(mapRect),
        visible_map_ratio: mapRect && panelRect ? Math.max(0, mapHeight - panelOverlap) / viewport.height : null,
        small_targets: undersized,
        geometry_state: document.body.dataset.tsirdDroughtGeometry || null,
        viewport_content: viewportMeta ? viewportMeta.getAttribute('content') || '' : '' };
    }""")
        metrics["requests"] = requests
        metrics["url"] = url
        return metrics
    finally:
        page.remove_listener("request", on_request)


def verdict(metrics: dict, route: str, criteria: dict) -> list[str]:
    c = criteria["criteria"]
    failures = []
    overflow = c["horizontal_overflow_px"]["target"]
    header_height = c["header_height_px"]["target"]
    title_lines = c["title_lines"]["target"]
    panel_ratio = c["panel_visible_map_ratio"]["target"]
    if metrics["scroll_width"] > metrics["client_width"] + overflow:
        failures.append(f"horizontal overflow {metrics['scroll_width']} > {metrics['client_width']}+{overflow}")
    if metrics["header_height"] > header_height:
        failures.append(f"header {metrics['header_height']:.1f}px > {header_height}px")
    if metrics["title_lines"] is not None and metrics["title_lines"] > title_lines:
        failures.append(f"title occupies {metrics['title_lines']} lines > {title_lines}")
    if metrics["small_targets"]:
        examples = ", ".join(
            f"{item['tag']}:{item['text'] or '(unlabelled)'} {item['width']:.0f}x{item['height']:.0f}"
            for item in metrics["small_targets"][:5]
        )
        failures.append(f"{len(metrics['small_targets'])} visible interactive targets fail the 44px-or-8px-spacing rule ({examples})")
    if route == "/map/drought/":
        if metrics["geometry_state"] != "ready":
            failures.append(f"display geometry did not become ready (state={metrics['geometry_state']!r})")
        if not metrics["map_present"] or not metrics["panel_present"] or metrics["visible_map_ratio"] is None:
            failures.append("cannot measure visible map ratio: required map or open panel is absent")
        elif metrics["visible_map_ratio"] < panel_ratio:
            failures.append(f"visible map ratio {metrics['visible_map_ratio']:.2f} < {panel_ratio}")
    viewport_content = metrics["viewport_content"].lower()
    if "user-scalable=no" in viewport_content or "maximum-scale=" in viewport_content and any(
        float(value) < 5 for value in re.findall(r"maximum-scale\s*=\s*([0-9.]+)", viewport_content)
    ):
        failures.append("viewport meta prevents required zoom")
    if route == "/map/drought/table/":
        hosts = {urlparse(item).hostname for item in metrics["requests"]}
        forbidden = set(c["table_forbidden_hosts"]) & hosts
        paths = [item for item in metrics["requests"] if any(part in item for part in c["table_forbidden_path_fragments"])]
        if forbidden or paths:
            failures.append(f"table route loaded forbidden map resources: hosts={sorted(forbidden)}, paths={paths}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--archive", action="store_true")
    parser.add_argument("--label", default="", help="optional safe label for an archived run, e.g. stage2")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    config = json.loads(CRITERIA.read_text(encoding="utf-8"))
    base = (args.base_url or config["base_url"]).rstrip("/")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is required: pip install playwright && playwright install chromium", file=sys.stderr)
        return 2
    results = []
    failures = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        toolchain = {
            "harness_version": HARNESS_VERSION,
            "playwright_version": package_version("playwright"),
            "chromium_version": browser.version,
        }
        page = browser.new_page()
        for name, viewport in config["viewports"].items():
            for route in config["routes"]:
                result = measure(page, base + route, viewport["width"], viewport["height"], config)
                result.update({"route": route, "viewport": name, "mode": viewport["mode"]})
                result["failures"] = verdict(result, route, config)
                failures += len(result["failures"]) if viewport["mode"] == "enforce" else 0
                results.append(result)
                print(f"{name} {route}: {'PASS' if not result['failures'] else '; '.join(result['failures'])}")
        browser.close()
    if args.archive:
        label = re.sub(r"[^a-z0-9-]+", "-", args.label.lower()).strip("-")
        if args.label and not label:
            parser.error("--label must contain at least one letter or digit")
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = f"-{label}" if label else ""
        path = ARCHIVE / f"{stamp}-stage-2-usability{suffix}.json"
        path.write_text(json.dumps({"criteria": config["schema_version"], "base_url": base, "label": label or None, "toolchain": toolchain, "results": results}, indent=2) + "\n", encoding="utf-8")
        print(f"archived {path.relative_to(ROOT)}")
    return 1 if args.check and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
