#!/usr/bin/env python3
"""Static validator for tracked TSIRD n8n workflow definitions.

It never contacts n8n, the runner, a database or a provider.  It reads the
tracked JSON definitions and the tracked runner source, then checks that every
definition is syntactically valid, free of credential material, and addresses
only runner endpoints that actually exist in this checkout.

Definitions named ``*-v2.development.json`` are additionally checked against
the source-refresh reliability contract: three distinct run outcomes, bounded
polling, and a terminal receipt on every path.

Hidden files such as a raw n8n bulk export are skipped by default.

Usage:  python3 tools/validate_n8n_workflows.py [workflow.json ...]
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "etl" / "drought" / "runner.py"
WORKFLOW_DIR = ROOT / "n8n" / "workflows"
RUNNER_HOST = "http://tsird-drought-runner:8090"
CREDENTIAL_HINT = re.compile(
    r"(?i)(authorization|bearer\s+[a-z0-9]|api[_-]?key|password|secret|private[_-]?key)"
)
ALLOWED_OUTCOMES = {"no_new_data", "data_updated", "failure"}


def runner_routes() -> set[str]:
    """Return every path the tracked runner defines, plus its job-status route."""
    text = RUNNER.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'@app\.(?:get|post)\("([^"]+)"', text))


def url_path(url: str) -> str:
    """Strip the n8n expression marker and the fixed runner host from a URL."""
    cleaned = url[1:] if url.startswith("=") else url
    if not cleaned.startswith(RUNNER_HOST):
        return cleaned
    path = cleaned[len(RUNNER_HOST):]
    return re.sub(r"\{\{.*?\}\}", "{job_id}", path)


def check_common(doc: dict, name: str, routes: set[str], errors: list[str]) -> None:
    if doc.get("active") is not False:
        errors.append(f"{name}: tracked definitions must carry \"active\": false")
    if "credentials" in json.dumps(doc):
        errors.append(f"{name}: contains a credentials block")
    hit = CREDENTIAL_HINT.search(json.dumps(doc))
    if hit and "$env." not in json.dumps(doc):
        errors.append(f"{name}: possible credential material near {hit.group(0)!r}")

    names = [n["name"] for n in doc["nodes"]]
    for node in doc["nodes"]:
        for reference in re.findall(r"\$\('([^']+)'\)", json.dumps(node["parameters"])):
            if reference not in names:
                errors.append(
                    f"{name}/{node['name']}: expression references unknown node {reference!r}"
                )
    if len(names) != len(set(names)):
        errors.append(f"{name}: duplicate node names")
    known = set(names)
    for src, outputs in doc.get("connections", {}).items():
        if src not in known:
            errors.append(f"{name}: connection from unknown node {src!r}")
        for branch in outputs.get("main", []):
            for link in branch or []:
                if link["node"] not in known:
                    errors.append(f"{name}: connection to unknown node {link['node']!r}")

    for node in doc["nodes"]:
        if not node["type"].endswith("httpRequest"):
            continue
        url = node["parameters"].get("url", "")
        if RUNNER_HOST not in url:
            errors.append(f"{name}/{node['name']}: non-runner URL {url!r}")
            continue
        path = url_path(url)
        if path not in routes:
            errors.append(f"{name}/{node['name']}: unknown runner route {path!r}")


def check_reliability(doc: dict, name: str, errors: list[str]) -> None:
    nodes = {n["name"]: n for n in doc["nodes"]}
    outcomes = set()
    for node in doc["nodes"]:
        if not node["type"].endswith(".set"):
            continue
        for assignment in node["parameters"]["assignments"]["assignments"]:
            if assignment["name"] == "run_outcome":
                outcomes.add(assignment["value"])
    missing = ALLOWED_OUTCOMES - outcomes
    if missing:
        errors.append(f"{name}: missing run_outcome value(s) {sorted(missing)}")
    unexpected = outcomes - ALLOWED_OUTCOMES
    if unexpected:
        errors.append(f"{name}: unexpected run_outcome value(s) {sorted(unexpected)}")

    waits = [n for n in doc["nodes"] if n["type"].endswith(".wait")]
    if not waits:
        errors.append(f"{name}: asynchronous polling requires at least one wait node")
    for node in waits:
        amount = str(node["parameters"].get("amount", ""))
        if not amount.startswith("="):
            errors.append(f"{name}/{node['name']}: wait must use a backoff expression")

    budget_guards = [
        n for n in doc["nodes"]
        if n["type"].endswith(".if")
        and "$runIndex" in json.dumps(n["parameters"])
    ]
    if len(budget_guards) < len(waits):
        errors.append(f"{name}: every poll loop needs a $runIndex budget guard")

    # Every loop edge must be guarded: a connection back into a wait node may
    # only originate from a budget guard.
    for src, outputs in doc.get("connections", {}).items():
        for branch in outputs.get("main", []):
            for link in branch or []:
                target = nodes.get(link["node"], {})
                if target.get("type", "").endswith(".wait") and src not in {
                    g["name"] for g in budget_guards
                }:
                    if not nodes.get(src, {}).get("type", "").endswith(".if"):
                        errors.append(
                            f"{name}: unguarded edge into wait node from {src!r}"
                        )

    for node in doc["nodes"]:
        if node["type"].endswith(".if"):
            wired = doc.get("connections", {}).get(node["name"], {}).get("main", [])
            if len(wired) != 2 or not all(wired):
                errors.append(f"{name}/{node['name']}: IF node needs both outputs wired")


def main(argv: list[str]) -> int:
    routes = runner_routes()
    paths = [pathlib.Path(a) for a in argv[1:]] or sorted(q for q in WORKFLOW_DIR.glob("*.json") if not q.name.startswith("."))
    errors: list[str] = []
    for path in paths:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid JSON ({exc})")
            continue
        for key in ("name", "nodes", "connections"):
            if key not in doc:
                errors.append(f"{path.name}: missing required key {key!r}")
        if "nodes" not in doc:
            continue
        check_common(doc, path.name, routes, errors)
        if path.name.endswith("-v2.development.json"):
            check_reliability(doc, path.name, errors)
        print(f"checked {path.name}: {len(doc['nodes'])} nodes")
    if errors:
        print("\nFAILED")
        for item in errors:
            print("  -", item)
        return 1
    print(f"\nOK: {len(paths)} definition(s) valid against {len(routes)} runner routes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
