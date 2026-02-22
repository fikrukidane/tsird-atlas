# TSIRD Atlas Data Engineering Pipeline Documentation

**Status**: Operational (Private Deployment)  
**Version**: 1.0  
**Date**: 2026-02-22

---

## Documentation Overview

This directory contains comprehensive technical documentation for the TSIRD Atlas Data Engineering Pipeline—a Docker-based geospatial ETL system built with Docker, Python, GDAL, and MapServer.

### Core Documents

| Document | Purpose | Audience | Lines |
|----------|---------|----------|-------|
| [**TSIRD_ATLAS_PIPELINE_ARCHITECTURE.md**](TSIRD_ATLAS_PIPELINE_ARCHITECTURE.md) | System design, principles, data flow | Architects, Engineers | 684 |
| [**TSIRD_PIPELINE_FLOW_DIAGRAM.md**](TSIRD_PIPELINE_FLOW_DIAGRAM.md) | Visual workflows, stage diagrams | All technical roles | 560 |
| [**TSIRD_OPERATIONS_GUIDE.md**](TSIRD_OPERATIONS_GUIDE.md) | Day-to-day operations, runbooks | DevOps, Operators | 561 |
| [**TSIRD_TROUBLESHOOTING.md**](TSIRD_TROUBLESHOOTING.md) | Error diagnosis, recovery procedures | Support, Incident response | 1109 |

**Total**: ~2900 lines of production-grade documentation

---

## Quick Navigation

### For New Engineers
1. Start with [Architecture](TSIRD_ATLAS_PIPELINE_ARCHITECTURE.md) (system overview)
2. Review [Flow Diagrams](TSIRD_PIPELINE_FLOW_DIAGRAM.md) (understand pipeline stages)
3. Read [Operations Guide](TSIRD_OPERATIONS_GUIDE.md) (practical commands)

### For Operators
- **Daily checks**: [Operations Guide §Monitoring](TSIRD_OPERATIONS_GUIDE.md#monitoring--health-checks)
- **Pipeline execution**: [Operations Guide §Running](TSIRD_OPERATIONS_GUIDE.md#running-the-pipeline)
- **When things break**: [Troubleshooting §Quick Diagnostic Tree](TSIRD_TROUBLESHOOTING.md#quick-diagnostic-tree)

### For Architects/Reviewers
- **Design decisions**: [Architecture §Principles](TSIRD_ATLAS_PIPELINE_ARCHITECTURE.md#architecture-principles)
- **Data quality**: [Architecture §Quality Framework](TSIRD_ATLAS_PIPELINE_ARCHITECTURE.md#data-quality-framework)
- **Lessons learned**: [Troubleshooting §Lessons Learned](TSIRD_TROUBLESHOOTING.md#lessons-learned--error-prevention)

---

## Repository Structure

```
/data (not committed to git)
	raw/
	normalized/
	gold/
Docker Projects/
	TSIRD-Atlas-Data-Pipeline/
mapserver/
docs/
docker-compose.yml
```

Data under /data is not committed; the repository contains pipeline logic, configuration, and documentation.

---

## System Summary

**What it does**: Ingests raw geospatial data (shapefiles/rasters), validates/normalizes to EPSG:4326, separates by region (Ethiopia-wide vs Tigray-only), exposes via OGC WMS/WFS.
Vector layers are normalized/validated by the Python pipeline; rasters (e.g., DEM/slope/web rasters) are managed and served via MapServer with explicit CRS definitions.

**Key Features**:
- ✅ **Reproducible**: No manual fixes; all operations logged
- ✅ **CRS-Safe**: Explicit overrides; guaranteed EPSG:4326 output
- ✅ **Geometry-Validated**: 98% validity threshold with auto-repair
- ✅ **Quarantine Model**: Failed layers isolated with full diagnostics
- ✅ **Docker-First**: Self-contained stack; no host GIS dependencies

**Pipeline Stages**:
1. **Raw Inventory Audit** → Detect CRS/geometry issues
2. **CRS Normalization** → Reproject to EPSG:4326, repair geometries
3. **Regional Separation** → Classify & clip Tigray vs Ethiopia-wide
4. **MapServer Integration** → Expose via WMS/WFS

**Tech Stack**: Docker Compose, Python 3.11, GeoPandas, GDAL, PostgreSQL 16 + PostGIS 3.4, MapServer 8.6.0

---

## Documentation Principles

This documentation follows engineering documentation standards:

- **Concise**: Technical accuracy without verbosity
- **Actionable**: Commands you can copy-paste
- **Indexed**: Table of contents + cross-references
- **Maintained**: Version numbers + changelogs
- **Practical**: Real error messages, actual file paths

**Writing Style**: Professional technical writing; no marketing language; assumes reader is experienced with GIS/Docker.

---

## Recent Updates

### 2026-02-22
- **Refinement pass**: Reduced redundancy, tightened language
- **Technical accuracy**: Preserved all commands, paths, and specifications
- **Line reduction**: ~15-20% reduction in verbosity while maintaining completeness

### 2026-02-21
- **Initial release**: Complete documentation suite (Architecture, Flow, Operations, Troubleshooting)
- **Production incidents captured**: Point layer rendering, CRS projection issues documented

---

## Contributing

When updating documentation:
1. Maintain technical accuracy (verify all commands)
2. Update version numbers and dates
3. Keep examples realistic (use actual layer names, paths)
4. Cross-reference related sections
5. Test all code blocks in actual environment

---

## License

Internal documentation for TSIRD project.

