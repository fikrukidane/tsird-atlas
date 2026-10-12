#!/usr/bin/env python3
"""Fail a release check when an advertised public WMS layer cannot render.

This is intentionally read-only. It requests GetCapabilities, then a tiny PNG
for every named leaf layer advertised by that exact WMS endpoint. It is suited
to post-deploy smoke checks, where a missing production table must fail the
release check instead of becoming a visitor-facing layer error.
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def request(url: str, params: dict[str, str], timeout: int) -> tuple[bytes, str]:
    query = urllib.parse.urlencode(params)
    separator = "&" if "?" in url else "?"
    with urllib.request.urlopen(f"{url}{separator}{query}", timeout=timeout) as response:
        return response.read(), response.headers.get_content_type()


def leaf_layer_names(capabilities: bytes) -> list[str]:
    root = ET.fromstring(capabilities)
    names: set[str] = set()
    for layer in root.findall(".//{*}Layer"):
        name = layer.findtext("{*}Name")
        child_layers = layer.findall("{*}Layer")
        if name and not child_layers:
            names.add(name)
    return sorted(names)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="public or loopback /map/ogc endpoint")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    try:
        capabilities, content_type = request(args.url, {"SERVICE": "WMS", "REQUEST": "GetCapabilities", "VERSION": "1.3.0"}, args.timeout)
        if "xml" not in content_type and not capabilities.lstrip().startswith(b"<"):
            raise RuntimeError("GetCapabilities did not return XML")
        names = leaf_layer_names(capabilities)
    except Exception as error:
        print(f"ERROR: capabilities check failed: {error}", file=sys.stderr)
        return 1
    failures = []
    for name in names:
        try:
            image, content_type = request(args.url, {
                "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0",
                "LAYERS": name, "STYLES": "", "CRS": "EPSG:4326",
                "BBOX": "36.3,12.2,40.3,14.9", "WIDTH": "8", "HEIGHT": "8",
                "FORMAT": "image/png", "TRANSPARENT": "TRUE",
            }, args.timeout)
            if content_type != "image/png" or not image.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError(f"expected PNG, got {content_type}")
        except Exception as error:
            failures.append(f"{name}: {error}")
    if failures:
        print("ERROR: public WMS render failures:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"OK: {len(names)} advertised public WMS layers rendered as PNG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
