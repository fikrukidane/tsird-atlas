"""Publish a stable, display-ready native-grid evidence raster.

The input file remains the preserved provider artifact.  This module creates a
single-band physical-value derivative under ``/data/drought/published`` for
MapServer.  The native grid is preserved; only provider band encoding and
data-mask semantics are made explicit.  Atomic replacement prevents MapServer
from reading a partially written file during a local refresh.
"""
import argparse
from pathlib import Path

import numpy as np
import rasterio


NODATA = -9999.0


def _write(target, profile, values):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    profile.update(count=1, dtype="float32", nodata=NODATA, compress="deflate")
    with rasterio.open(temporary, "w", **profile) as destination:
        destination.write(values.astype("float32"), 1)
    temporary.replace(target)


def publish_provider_band(source_path, target_path, band, scale, offset, mask_band):
    """Convert one source band to physical units without resampling it."""
    with rasterio.open(source_path) as source:
        raw = np.array(source.read(band), dtype="float32", copy=True)
        mask = source.read(mask_band) > 0 if mask_band else source.read_masks(band) > 0
        if source.nodata is not None:
            mask &= raw != source.nodata
        values = raw * scale + offset
        values[~mask | ~np.isfinite(values)] = NODATA
        _write(Path(target_path), source.profile.copy(), values)


def publish_rainfall_total(source_paths, target_path):
    """Sum same-grid CHIRPS rainfall depths, retaining only complete cells."""
    paths = [Path(path) for path in source_paths]
    if not paths:
        raise ValueError("at least one CHIRPS source raster is required")
    with rasterio.open(paths[0]) as first:
        profile = first.profile.copy()
        total = np.zeros((first.height, first.width), dtype="float32")
        complete = np.ones((first.height, first.width), dtype=bool)
        reference = (first.width, first.height, first.transform, first.crs)
    for path in paths:
        with rasterio.open(path) as source:
            if (source.width, source.height, source.transform, source.crs) != reference:
                raise ValueError("CHIRPS source grids do not match")
            values = np.array(source.read(1), dtype="float32", copy=True)
            valid = source.read_masks(1) > 0
            if source.nodata is not None:
                valid &= values != source.nodata
            total[valid] += values[valid]
            complete &= valid
    total[~complete] = NODATA
    _write(Path(target_path), profile, total)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", required=True, choices=("ndvi", "swi040", "lst", "chirps-total"))
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    if args.kind == "ndvi":
        publish_provider_band(args.source[0], args.target, band=1, scale=1 / 250, offset=-0.08, mask_band=3)
    elif args.kind == "swi040":
        publish_provider_band(args.source[0], args.target, band=2, scale=0.5, offset=0, mask_band=5)
    elif args.kind == "lst":
        publish_provider_band(args.source[0], args.target, band=1, scale=0.01, offset=0, mask_band=5)
    else:
        publish_rainfall_total(args.source, args.target)


if __name__ == "__main__":
    main()
