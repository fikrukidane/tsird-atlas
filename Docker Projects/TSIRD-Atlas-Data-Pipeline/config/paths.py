from pathlib import Path

# Locked architectural constants (container-absolute)
DATA_ROOT = Path("/work/data")
RAW_ROOT = DATA_ROOT / "raw"
NORMALIZED_ROOT = DATA_ROOT / "normalized"
GOLD_ROOT = DATA_ROOT / "gold" / "atlas_4326"

# Raw source-of-truth vectors
VECTORS_RAW_ROOT = RAW_ROOT / "vectors"

# Pipeline project (logic + reports only; no data copies)
PROJECT_ROOT = Path("/work/Docker Projects/TSIRD-Atlas-Data-Pipeline")
REPORT_ROOT = PROJECT_ROOT / "reports"
AUDIT_ROOT = REPORT_ROOT / "audit"
