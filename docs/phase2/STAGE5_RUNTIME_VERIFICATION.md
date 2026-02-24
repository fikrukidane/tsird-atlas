# Phase 2 - Step 2: Stage 5 Runtime Verification Checklist

**Purpose**: Validate that MapServer implementation satisfies Stage 5 specification before frontend integration.

**Frozen Reference**: [MAPSERVER_MODULARIZATION.md](MAPSERVER_MODULARIZATION.md)

**Test Date**: 2026-02-24  
**WMS Endpoint**: `http://localhost:8080/map/ogc` (or current deployment)

---

## Pre-Test Setup

- [ ] **Checkpoint A**: MapServer (8.6+) running with tsird.map loaded
- [ ] **Checkpoint B**: GetCapabilities endpoint responds (HTTP 200)
- [ ] **Checkpoint C**: WMS GetMap returns PNG tiles (no errors)
- [ ] **Checkpoint D**: test-registry-good.yaml passes Stage 4 validation

---

## 8-Point Acceptance Criteria (Stage 5)

### Criterion 1: No Inline Layers in Master Mapfile

**Requirement**: `tsird.map` contains only configuration directives and INCLUDE statements. Zero inline LAYER blocks.

**Test Command**:
```bash
grep -c "^\s*LAYER\s*$" db/mapfiles/tsird.map
```

**Expected Result**: `0` (no inline layers)

**Observed Result**: ___________

- [ ] **PASS**: No inline layers found
- [ ] **FAIL**: Inline layers detected

---

### Criterion 2: Published Layers Have STATUS ON

**Requirement**: Every layer with `published: true` in registry has `STATUS ON` in mapfile.

**Test Procedure**:
1. Extract published layer list from test-registry-good.yaml:
   ```bash
   grep -A 2 'published: true' tools/test-registry-good.yaml | grep 'wms_name:' | awk '{print $NF}' > /tmp/published_layers.txt
   ```
2. For each published layer, verify mapfile contains `STATUS ON`:
   ```bash
   for wms_name in $(cat /tmp/published_layers.txt); do
     echo "Checking $wms_name..."
     grep -A 5 "NAME \"$wms_name\"" db/mapfiles/*.map | grep "STATUS ON" && echo "✓" || echo "✗"
   done
   ```

**Expected Result**: All layers marked ✓

**Observed Result**: ___________

- [ ] **PASS**: All published layers have STATUS ON
- [ ] **FAIL**: Some published layers missing STATUS ON

---

### Criterion 3: GetCapabilities Reflects Only Published Layers

**Requirement**: WMS GetCapabilities response lists only layers with `published: true`.

**Test Procedure**:
1. Fetch GetCapabilities:
   ```bash
   curl -s "http://localhost:8080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities" > /tmp/capabilities.xml
   ```
2. Extract layer names:
   ```bash
   grep "<Name>" /tmp/capabilities.xml | sed 's/<[^>]*>//g' | sort > /tmp/getcap_layers.txt
   ```
3. Extract published layers from registry:
   ```bash
   grep -A 2 'published: true' tools/test-registry-good.yaml | grep 'wms_name:' | awk '{print $NF}' | sort > /tmp/published_layers.txt
   ```
4. Compare:
   ```bash
   diff -u /tmp/published_layers.txt /tmp/getcap_layers.txt
   ```

**Expected Result**: No differences (files identical)

**Observed Result**: ___________

- [ ] **PASS**: GetCapabilities matches published layers exactly
- [ ] **FAIL**: Mismatch (orphans or missing layers)

**Mismatch Details**: ___________

---

### Criterion 4: Scale Mutex Enforcement (Server-Side)

**Requirement**: MapServer layer STATUS respects scale rules. Dual-scale layers (national_roads / tigray_roads) never both render at same scale.

**Test Data**:
- National roads: min=50M, max=500k
- Tigray roads: min=490k, max=50k

**Test Procedure** (requires GetMap with scale rules):
1. Request map at scale 1M (both eligible if overlap exists):
   ```bash
   # Scale 1M = typical zoom where both might be visible
   curl -s "http://localhost:8080/map/ogc?SERVICE=WMS&REQUEST=GetMap&LAYERS=national_roads,tigray_roads&BBOX=...&WIDTH=256&HEIGHT=256&SRS=EPSG:3857&FORMAT=image/png" > /tmp/map_1m.png
   ```
2. Check pixel data (manual inspection or analysis tool):
   - If both layers render at same scale: **FAIL** (colors/features indicate overlap)
   - If only one renders: **PASS**

**Expected Result**: At scale 1M, only national_roads renders (tigray_roads is out of scale)

**Observed Result**: ___________

- [ ] **PASS**: Mutex enforced (only one layer visible at overlapping scales)
- [ ] **FAIL**: Both layers visible (mutex not enforced)

---

### Criterion 5: Layer Count Identity

**Requirement**: Number of layers in GetCapabilities == number of published layers in registry.

**Test Procedure**:
1. Count GetCapabilities layers:
   ```bash
   grep -c "<Name>" /tmp/capabilities.xml
   ```
2. Count published in registry:
   ```bash
   grep -c 'published: true' tools/test-registry-good.yaml
   ```
3. Compare counts

**Expected Result**: Counts match (e.g., both = 6)

**Registry Published Layers**: ___________  
**GetCapabilities Count**: ___________  
**Match**: [ ] Yes [ ] No

- [ ] **PASS**: Counts match exactly
- [ ] **FAIL**: Mismatch

---

### Criterion 6: No Phase 1 Data Changes

**Requirement**: Gold tables and production data remain untouched by Stage 5 work.

**Test Procedure**:
1. Check gold table record counts (snap to Phase 1 baseline):
   ```bash
   # Sample check (if database accessible)
   psql -d tsird -c "SELECT COUNT(*) FROM gold.roads;"
   psql -d tsird -c "SELECT COUNT(*) FROM gold.aoi_ethiopia;"
   ```
2. Compare against STRUCTURE_ANALYSIS.md baseline

**Phase 1 Baseline (from STRUCTURE_ANALYSIS.md)**:
- gold.roads: _________ records
- gold.aoi_ethiopia: _________ records

**Observed Counts**:
- gold.roads: _________ records
- gold.aoi_ethiopia: _________ records

- [ ] **PASS**: Counts unchanged from baseline
- [ ] **FAIL**: Data was modified (requires rollback)

---

### Criterion 7: Thematic Organization + Include Order Preserved

**Requirement**: Mapfile include order matches expected structure (globals → thematic modules → no private includes).

**Test Procedure**:
```bash
cat db/mapfiles/tsird.map | grep "^INCLUDE" | head -10
```

**Expected Output** (or similar structure):
```
INCLUDE "00_globals.map"
INCLUDE "01_outputformats.map"
INCLUDE "02_web_metadata.map"
INCLUDE "layers_administrative.map"
INCLUDE "layers_transport.map"
INCLUDE "layers_health.map"
...
```

**No includes of `90_private_or_deprecated.map`** (that file exists but is not included in active mapfile).

**Observed Include Order**: 
```
___________
___________
___________
```

- [ ] **PASS**: Includes are in correct order (thematic modules only)
- [ ] **FAIL**: Include order wrong or private layers included

---

### Criterion 8: All Tests Pass (Automated + Manual)

**Requirement**: Full validation suite passes without warnings or errors.

**Automated Tests** (if CI pipeline exists):
```bash
make test-mapserver
# or
pytest test/test_mapserver.py
```

**Expected Result**: All tests pass (0 failures, 0 skipped)

**Observed Result**: ___________

- [ ] **PASS**: All tests pass
- [ ] **FAIL**: Test failures
- [ ] **N/A**: No automated test suite yet

**Manual Verification Checksum**:
```
Criterion 1: [ ] PASS  [ ] FAIL
Criterion 2: [ ] PASS  [ ] FAIL
Criterion 3: [ ] PASS  [ ] FAIL
Criterion 4: [ ] PASS  [ ] FAIL
Criterion 5: [ ] PASS  [ ] FAIL
Criterion 6: [ ] PASS  [ ] FAIL
Criterion 7: [ ] PASS  [ ] FAIL
Criterion 8: [ ] PASS  [ ] FAIL

Overall: [ ] ALL PASS (Stage 5 verified) [ ] FAIL (blockers found)
```

---

## Test Execution Log

**Tester**: ___________  
**Date**: ___________  
**Environment**: ___________  
**MapServer Version**: ___________  

### Issues Found (if any)

| Criterion | Issue | Resolution | Status |
|---|---|---|---|
| | | | |
| | | | |

---

## Sign-Off

**Stage 5 Runtime Verification**: [ ] APPROVED (all criteria pass) [ ] BLOCKED (failures found)

**Verified By**: ___________ (Signature/Handle)  
**Approval Date**: ___________

---

## Next Steps

- [ ] If **APPROVED**: Proceed to Step 3 (Stage 6 Milestone 1 — Frontend)
- [ ] If **BLOCKED**: Fix MapServer issues, re-run checklist

---

**✓ END OF STAGE 5 RUNTIME VERIFICATION CHECKLIST**

This verification ensures Stage 5 (MapServer Modularization) contracts hold under production conditions before Phase 2 frontend development begins.
