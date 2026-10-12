#!/usr/bin/env python3
"""Generate the production-only MapServer vector include.

Development and production share the base mapfile, but production has no
development drought tables or raster paths.  This generator preserves every
other vetted Atlas layer verbatim and removes the contiguous development-only
block before deployment.  The resulting file is mounted over the base include
only by ``docker-compose.production.yml``.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "infra" / "mapserver" / "mapfiles" / "includes" / "vectors_gold.map"
OUTPUT = ROOT / "infra" / "mapserver" / "mapfiles" / "includes" / "vectors_public.map"
START = "# Development-only CHIRPS v3 seasonal rainfall-condition summary."
END = 'LAYER\n  NAME "ethiopia_woredas"'


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    start = source.find(START)
    end = source.find(END, start)
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError("could not locate the development-only MapServer layer block")
    result = (
        source[:start]
        + "# Development-only drought layers are omitted from the production WMS.\n"
        + "# Public retained rasters are defined separately in drought_public_rasters.map.\n\n"
        + source[end:]
    )
    result = "\n".join(line.rstrip() for line in result.splitlines()) + "\n"
    if 'NAME "tigray_drought_' in result or "_dev" in result:
        raise RuntimeError("production include still contains a development drought layer")
    if 'NAME "tigray_tabias_ti_en_pg"' not in result or 'NAME "tigray_woredas_ti_en_pg"' not in result:
        raise RuntimeError("production include lost required bilingual Atlas context layers")
    OUTPUT.write_text(result, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} without development drought layers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
