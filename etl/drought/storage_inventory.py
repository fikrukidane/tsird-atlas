"""Report bounded TSIRD Drought Intelligence storage use without changing data.

This is intentionally an inventory, not a retention or archive command. It
walks only known drought-data directories so an operator can review capacity
before proposing any archive or deletion action.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


# These are the actual managed paths used by the current drought pipelines.
# Keep this list explicit: broad traversal of /data could include unrelated
# Atlas datasets and make both the report and future retention decisions unsafe.
DIRECTORIES = ("cache", "raw", "published", "outputs", "worldcover", "worldpop")


def capacity_state(free_bytes: int, total_bytes: int) -> dict:
    """Classify available storage; this is reporting only, never a cleanup control."""
    free_gib = free_bytes / (1024 ** 3)
    free_percent = (free_bytes / total_bytes * 100) if total_bytes else 0.0
    if free_gib < 25 or free_percent < 5:
        status, action = "stop", "Block heavy acquisitions pending an approved, recoverable capacity action."
    elif free_gib < 50 or free_percent < 10:
        status, action = "critical", "Do not start new heavy backfills; prepare a reviewed archive proposal."
    elif free_gib < 100 or free_percent < 20:
        status, action = "warning", "Review storage before any new backfill or source expansion."
    else:
        status, action = "normal", "Capacity is within the local development operating threshold."
    return {
        "status": status,
        "free_percent": round(free_percent, 2),
        "operator_action": action,
        "read_only": True,
    }


def iso_timestamp(epoch: float | None) -> str | None:
    return None if epoch is None else datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def inventory_directory(root: Path, name: str) -> dict:
    target = root / name
    result = {"directory": name, "exists": target.is_dir(), "files": 0,
              "bytes": 0, "oldest_modified": None, "newest_modified": None}
    if not target.is_dir():
        return result
    oldest = newest = None
    for path in target.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        result["files"] += 1
        result["bytes"] += stat.st_size
        oldest = stat.st_mtime if oldest is None else min(oldest, stat.st_mtime)
        newest = stat.st_mtime if newest is None else max(newest, stat.st_mtime)
    result["oldest_modified"] = iso_timestamp(oldest)
    result["newest_modified"] = iso_timestamp(newest)
    return result


def build_inventory(root: Path) -> dict:
    """Return a JSON-safe inventory without writing an inventory artifact."""
    entries = [inventory_directory(root, name) for name in DIRECTORIES]
    filesystem = os.statvfs(root)
    free_bytes = filesystem.f_frsize * filesystem.f_bavail
    total_bytes = filesystem.f_frsize * filesystem.f_blocks
    return {
        "data_root_exists": root.is_dir(),
        "directories": entries,
        "total_managed_bytes": sum(item["bytes"] for item in entries),
        "filesystem_free_bytes": free_bytes,
        "filesystem_total_bytes": total_bytes,
        "capacity": capacity_state(free_bytes, total_bytes),
        "read_only": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="/data/drought")
    args = parser.parse_args()
    root = Path(args.data_root)
    print(json.dumps({
        "kind": "drought-storage-inventory",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **build_inventory(root),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
