"""Discover FEWS NET's public Ethiopia classification assets without ingesting them.

This is deliberately a provider-context gate. It identifies the official
publication page and any linked GeoJSON/ZIP assets, retaining only a compact
receipt for a human review of issue period, scenario, licence, and native
Food Security Classification (FSC) geography. It never downloads a spatial
asset, maps a provider class to a Tabia, or creates a TSIRD classification.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


CATALOGUE_URL = "https://fews.net/data/acute-food-insecurity"
FALLBACK_PUBLICATION_URL = (
    "https://fews.net/ethiopia-acute-food-insecurity-classification-"
    "february-2026-september-2026"
)
RECEIPT = Path("/data/drought/outputs/fews-net-public-classification-discovery.json")
USER_AGENT = "TSIRD-Atlas-public-context-discovery/1.0 (+https://tigrayinsights.net)"


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "button-url", "src"} and value:
                self.hrefs.append(value)


def fetch(url: str) -> tuple[int, str, str]:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.headers.get_content_type(), response.read(1_000_000).decode("utf-8", errors="replace")


def absolute(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, href)


def ethiopia_publications(hrefs: list[str], base: str) -> list[str]:
    values = []
    for href in hrefs:
        url = absolute(base, href)
        if re.search(r"/ethiopia-(?:acute-)?food-insecurity-classification-", url, re.I):
            values.append(url)
    return list(dict.fromkeys(values))


def assets(hrefs: list[str], base: str) -> list[str]:
    values = []
    for href in hrefs:
        url = absolute(base, href)
        if urllib.parse.urlparse(url).path.lower().endswith((".geojson", ".json", ".zip", ".kml")):
            values.append(url)
    return list(dict.fromkeys(values))


def main() -> None:
    result = {
        "status": "manual_data_contract_review_required",
        "source": "FEWS NET",
        "product": "Acute Food Insecurity Classifications",
        "country": "Ethiopia",
        "catalogue_url": CATALOGUE_URL,
        "provider_geography": "FEWS NET Food Security Classification units; never TSIRD Tabias",
        "retained_provider_payload": False,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        catalogue_status, catalogue_type, catalogue_html = fetch(CATALOGUE_URL)
        parser = Links(); parser.feed(catalogue_html)
        publications = ethiopia_publications(parser.hrefs, CATALOGUE_URL)
        publication_url = publications[0] if publications else FALLBACK_PUBLICATION_URL
        publication_status, publication_type, publication_html = fetch(publication_url)
        publication_parser = Links(); publication_parser.feed(publication_html)
        found_assets = assets(publication_parser.hrefs, publication_url)
        result.update({
            "catalogue_http_status": catalogue_status,
            "catalogue_content_type": catalogue_type,
            "publication_url": publication_url,
            "publication_http_status": publication_status,
            "publication_content_type": publication_type,
            "ethiopia_publication_candidates": publications[:5],
            "asset_candidates": found_assets[:20],
            "geojson_candidates": [value for value in found_assets if urllib.parse.urlparse(value).path.lower().endswith((".geojson", ".json"))][:10],
            "reason": (
                "Official publication metadata and candidate asset links were discovered; no asset was downloaded or loaded."
                if found_assets else
                "Official publication metadata was discovered, but its public GIS asset links were not found in the page response."
            ),
            "next_gate": "A reviewer must select one provider issue, confirm issue/validity periods and data-use terms, then approve a bounded native-FSC download and validation run.",
        })
    except Exception as exc:
        result.update({
            "status": "unavailable",
            "reason": f"FEWS NET public classification discovery failed: {type(exc).__name__}",
            "next_gate": "Investigate provider reachability or access policy; do not substitute scraped maps, screenshots, or a Tabia proxy.",
        })
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
