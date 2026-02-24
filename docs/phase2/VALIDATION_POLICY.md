# Phase 2 - Stage 4: Validation Policy

**Generated**: 2026-02-24  
**Status**: ✓ VALIDATION POLICY FROZEN  
**Scope**: Registry YAML Validator Requirements & Enforcement Gates

---

## 1. Purpose

This document defines **how** the Phase 2 YAML registry (`atlas-registry.yaml`) is validated against the authoritative schema and constraints defined in [CONFIG_MODEL.md](CONFIG_MODEL.md).

**Validation is a hard gate** for Phase 2 implementation and deployment. No configuration can proceed to frontend implementation (Stage 6) without passing validator BLOCK checks.

**Key Principle**: Validation failures are deterministic, actionable, and enforceable at build time.

---

## 2. Validator Requirements

### 2.1 Tooling

**Implement one validator** (choose technology):

**Option A: Python** (recommended)
- Mature YAML tooling (`pyyaml`, `ruamel.yaml`)
- Speed of implementation
- Natural for constraint checking

**Option B: Node.js** (acceptable)
- Acceptable if project standard favors JS
- `yaml` or `js-yaml` library

**Input**:
- `atlas-registry.yaml` (path configurable via CLI argument)

**Output**:
- Exit code: 0 (PASS) or 1 (FAIL), plus structured report
- Console output (human-readable)
- Optional JSON output (machine consumption)

### 2.2 Execution Modes

```bash
# Default: validate loaded registry
validator atlas-registry.yaml

# Machine-readable output
validator --format json atlas-registry.yaml

# Strict mode: treat WARNs as BLOCKs
validator --warnings-as-errors atlas-registry.yaml

# Verbose: include rule descriptions and config analysis
validator --verbose atlas-registry.yaml
```

### 2.3 Deterministic Results

Validator must:
- **Be order-stable**: Same YAML input → same error list in same order
- **Produce actionable messages**: What failed, where (line/path), how to fix
- **Support offline execution**: No external API calls required
- **Have consistent formatting**: Errors parseable by CI/CD pipelines

---

## 3. Severity Model

### BLOCK (Validation Failure)

**Blocks** Phase 2 progress. Builder exits with code 1.

Used when a constraint violation breaks:
- Runtime behavior
- Security posture
- Architecture freeze
- Referential integrity
- Service contract

**Phase 2 Deployment Gate**: Must have **0 BLOCK errors** to proceed.

### WARN (Non-Fatal Advisory)

**Does not block**, but must be reviewed.

Used for:
- Quality issues (e.g., placeholder text in attribution)
- Policy hints (e.g., large visibility gap in scale ranges)
- Data quality flags (e.g., unused layers)

**Phase 2 Governance**: All WARNs must be resolved or **explicitly approved** before production deploy (manual sign-off required).

---

## 4. Constraints Enforced (Phase 2)

These correspond to the 7 frozen rules in [CONFIG_MODEL.md](CONFIG_MODEL.md#5-mandatory-global-validation-constraints). The validator MUST check all items below.

---

### Rule 1 — Referential Integrity

**Severity** : BLOCK

**Statement**: Every layer ID referenced in `categories[].groups[].layers[]` MUST exist as a key in `layers:`.

**Failure Examples**:
- `categories[0].groups[0].layers[2]` references `"ethiopia_kebeles"` but no `layers.ethiopia_kebeles` exists
- Orphan group with no backing layers
- Implicit references from deleted layer definitions

**Validator Logic**:
```python
def check_referential_integrity(registry):
    valid_layer_ids = set(registry['layers'].keys())
    for cat_idx, category in enumerate(registry['categories']):
        for grp_idx, group in enumerate(category['groups']):
            for layer_idx, layer_id in enumerate(group['layers']):
                if layer_id not in valid_layer_ids:
                    error(
                        severity='BLOCK',
                        rule='R1 Referential Integrity',
                        path=f'categories[{cat_idx}].groups[{grp_idx}].layers[{layer_idx}]',
                        message=f'Orphan layer reference: "{layer_id}" not found in layers map',
                        suggested_fix=f'Define layers.{layer_id} or remove ref from group'
                    )
```

---

### Rule 2 — Unique WMS Layer Names

**Severity**: BLOCK

**Statement**: Every `layers[*].wms_name` MUST be globally unique across the registry.

**Failure Example**:
- Two registry entries define `wms_name: "ethiopia_zones"` (MapServer would be ambiguous)

**Validator Logic**:
```python
def check_unique_wms_names(registry):
    wms_names = {}
    for layer_id, layer_def in registry['layers'].items():
        wms_name = layer_def.get('wms_name')
        if wms_name in wms_names:
            error(
                severity='BLOCK',
                rule='R2 Unique WMS Names',
                path=f'layers.{layer_id}.wms_name',
                message=f'Duplicate wms_name: "{wms_name}" (also used by layers.{wms_names[wms_name]})',
                suggested_fix='Rename one layer or consolidate into single entry'
            )
        wms_names[wms_name] = layer_id
```

---

### Rule 3 — Publication Governance

**Severity**: BLOCK (structural), WARN (policy)

**Statement**:
- If `published: false`, the layer MUST NOT appear in any `groups[].layers[]` list.
- Governance: `published` is immutable after first publication (process rule, not validator enforced).

**Failure Example**:
- `published: false` layer appears in group list → BLOCK
- `attribution: "<to-fill>"` on published layer → WARN (placeholder flag)

**Validator Logic**:
```python
def check_publication_rules(registry):
    for cat_idx, category in enumerate(registry['categories']):
        for grp_idx, group in enumerate(category['groups']):
            for layer_idx, layer_id in enumerate(group['layers']):
                layer_def = registry['layers'].get(layer_id)
                if not layer_def.get('published', True):  # Default: published=true
                    error(
                        severity='BLOCK',
                        rule='R3 Publication Governance',
                        path=f'categories[{cat_idx}].groups[{grp_idx}].layers[{layer_idx}]',
                        message=f'Unpublished layer "{layer_id}" appears in group',
                        suggested_fix='Set published: true or remove from group'
                    )
    
    # WARN: Placeholder text in attribution
    for layer_id, layer_def in registry['layers'].items():
        attr = layer_def.get('attribution', '')
        if '<to-fill>' in attr.lower() or 'tbd' in attr.lower():
            warn(
                rule='R3 Publication Governance',
                path=f'layers.{layer_id}.attribution',
                message='Placeholder text in attribution',
                suggested_fix='Replace with actual data source credit'
            )
```

---

### Rule 4 — Query Rules

**Severity**: BLOCK

**Statement**:
- If `queryable: true`, then `identify_fields` MUST exist and be **non-empty list**.
- If `queryable: false`, then `identify_fields` MUST be **empty list or omitted**.

**Failure Examples**:
- `queryable: true` with `identify_fields: []` → BLOCK
- `queryable: false` with `identify_fields: ["NAME", "CODE"]` → BLOCK
- Missing `identify_fields` key with `queryable: true` → BLOCK

**Validator Logic**:
```python
def check_query_rules(registry):
    for layer_id, layer_def in registry['layers'].items():
        queryable = layer_def.get('queryable', False)
        identify_fields = layer_def.get('identify_fields', [])
        
        if queryable and not identify_fields:
            error(
                severity='BLOCK',
                rule='R4 Query Rules',
                path=f'layers.{layer_id}',
                message='queryable=true but identify_fields is empty',
                suggested_fix='Add non-empty identify_fields list or set queryable: false'
            )
        
        if not queryable and identify_fields:
            error(
                severity='BLOCK',
                rule='R4 Query Rules',
                path=f'layers.{layer_id}',
                message='queryable=false but identify_fields is non-empty',
                suggested_fix='Clear identify_fields to [] or set queryable: true'
            )
```

---

### Rule 5 — Scale Convention Enforcement

**Severity**: BLOCK

**Statement**:
- If a layer defines scale constraints, `min_scale` and `max_scale` must be positive integers.
- **Cartographic convention MUST hold**: `min_scale > max_scale` (min is zoomed-out scale denominator, max is zoomed-in).

**Failure Examples**:
- `min_scale: 1000000, max_scale: 10000000` → BLOCK (reversed)
- `min_scale: 100.5` → BLOCK (float)
- `min_scale: -1000000` → BLOCK (negative)
- `max_scale: null` → BLOCK (invalid type)

**Validator Logic**:
```python
def check_scale_convention(registry):
    for layer_id, layer_def in registry['layers'].items():
        min_scale = layer_def.get('min_scale')
        max_scale = layer_def.get('max_scale')
        
        if min_scale is not None or max_scale is not None:
            # Both must be present if either exists (policy choice)
            if (min_scale is None) != (max_scale is None):
                warn(
                    rule='R5 Scale Convention',
                    path=f'layers.{layer_id}',
                    message='Only one of min_scale/max_scale defined; prefer both',
                    suggested_fix='Define both or neither'
                )
            
            # Type and range checks
            for key, val in [('min_scale', min_scale), ('max_scale', max_scale)]:
                if val is not None:
                    if not isinstance(val, int) or isinstance(val, bool):
                        error(
                            severity='BLOCK',
                            rule='R5 Scale Convention',
                            path=f'layers.{layer_id}.{key}',
                            message=f'{key} must be positive integer, got {type(val).__name__}',
                            suggested_fix=f'Convert {key} to integer'
                        )
                    elif val <= 0:
                        error(
                            severity='BLOCK',
                            rule='R5 Scale Convention',
                            path=f'layers.{layer_id}.{key}',
                            message=f'{key} must be positive, got {val}',
                            suggested_fix=f'Set {key} to positive denominator'
                        )
            
            # Cartographic convention check
            if min_scale is not None and max_scale is not None:
                if min_scale <= max_scale:
                    error(
                        severity='BLOCK',
                        rule='R5 Scale Convention',
                        path=f'layers.{layer_id}',
                        message=f'min_scale ({min_scale}) must be > max_scale ({max_scale})',
                        suggested_fix='Swap or correct scale values (cartographic convention: min=zoomed-out, max=zoomed-in)'
                    )
```

---

### Rule 6 — Scale Mutual Exclusion Pairs

**Severity**: BLOCK

**Statement**: For every pair in `rules.scale_mutex_pairs`, validate:
- Both layer IDs exist in layers
- Both layers define min_scale and max_scale
- Visible ranges do NOT overlap (under cartographic convention)
- Prefer exact boundary handoff (no gap)

**Overlap Detection** (deterministic test):

For each pair A, B:
- Represent visible range as interval: `[max_scale, min_scale]` (inverted order per cartographic convention)
- Two ranges overlap iff: `max(A.max, B.max) < min(A.min, B.min)` (strict <, so exact boundary is allowed)

**Failure Examples**:
- `ethiopia_roads: [500000, 50000000]`, `tigray_roads: [1000000, 100000]` → BLOCK (overlap in range 500k-100k)
- Exact handoff `ethiopia_roads: [500000, 50000000]`, `tigray_roads: [500000, 1]` → OK (handoff at 500k)
- Missing layer ID in pair → BLOCK (referential check applies here too)

**Validator Logic**:
```python
def check_scale_mutex_pairs(registry):
    pairs = registry.get('rules', {}).get('scale_mutex_pairs', [])
    for pair in pairs:
        if len(pair) != 2:
            error(
                severity='BLOCK',
                rule='R6 Scale Mutex',
                path='rules.scale_mutex_pairs',
                message=f'Pair must have exactly 2 elements, got {len(pair)}',
                suggested_fix='Correct pair definition'
            )
            continue
        
        layer_a_id, layer_b_id = pair
        layer_a = registry['layers'].get(layer_a_id)
        layer_b = registry['layers'].get(layer_b_id)
        
        # Check existence
        if not layer_a:
            error(
                severity='BLOCK',
                rule='R6 Scale Mutex',
                path='rules.scale_mutex_pairs',
                message=f'Layer "{layer_a_id}" not found',
                suggested_fix='Ensure layer exists or remove from pair'
            )
        if not layer_b:
            error(
                severity='BLOCK',
                rule='R6 Scale Mutex',
                path='rules.scale_mutex_pairs',
                message=f'Layer "{layer_b_id}" not found',
                suggested_fix='Ensure layer exists or remove from pair'
            )
        
        if not (layer_a and layer_b):
            continue
        
        # Check scale definitions
        for layer_id, layer in [(layer_a_id, layer_a), (layer_b_id, layer_b)]:
            if 'min_scale' not in layer or 'max_scale' not in layer:
                error(
                    severity='BLOCK',
                    rule='R6 Scale Mutex',
                    path=f'layers.{layer_id}',
                    message=f'Layer in mutex pair missing min_scale/max_scale',
                    suggested_fix=f'Define both min_scale and max_scale for {layer_id}'
                )
        
        if 'min_scale' not in layer_a or 'min_scale' not in layer_b:
            continue
        
        # Overlap test (strict <, so exact handoff allowed)
        a_min, a_max = layer_a['min_scale'], layer_a['max_scale']
        b_min, b_max = layer_b['min_scale'], layer_b['max_scale']
        
        # Ranges overlap if: max(a_max, b_max) < min(a_min, b_min)
        if max(a_max, b_max) < min(a_min, b_min):
            error(
                severity='BLOCK',
                rule='R6 Scale Mutex',
                path='rules.scale_mutex_pairs',
                message=f'Scales overlap: [{layer_a_id}=[{a_max},{a_min}], {layer_b_id}=[{b_max},{b_min}]',
                suggested_fix='Adjust scales to [A.max ≥ B.min] or [B.max ≥ A.min]'
            )
        
        # WARN: Large gap (optional)
        if max(a_max, b_max) < min(a_min, b_min) - 100000:
            warn(
                rule='R6 Scale Mutex',
                path='rules.scale_mutex_pairs',
                message=f'Large scale gap detected between {layer_a_id} and {layer_b_id}',
                suggested_fix='Consider adding intermediate zoom layer or documenting intentional gap'
            )
```

---

### Rule 7 — No Circular Nesting / Correct Structure

**Severity**: BLOCK

**Statement**: Registry structure MUST conform to:
- `categories[]` → `groups[]` → `layers[]`
- No categories referencing categories
- No groups containing groups
- Only forward references allowed

**Failure Examples**:
- Category with key `"groups"` = dict instead of array → BLOCK
- Group with nested `"groups"` key → BLOCK
- Invalid nesting keys detected → BLOCK

**Validator Logic**:
```python
def check_structure_integrity(registry):
    # Schema validation (handle via strict YAML schema or type checks)
    
    # Type checks for critical sections
    if not isinstance(registry.get('categories', []), list):
        error(
            severity='BLOCK',
            rule='R7 Structure Integrity',
            path='categories',
            message='categories must be array',
            suggested_fix='Convert to YAML array: categories: [...]'
        )
    
    for cat_idx, category in enumerate(registry.get('categories', [])):
        if not isinstance(category.get('groups', []), list):
            error(
                severity='BLOCK',
                rule='R7 Structure Integrity',
                path=f'categories[{cat_idx}].groups',
                message='groups must be array',
                suggested_fix='Convert to array: groups: [...]'
            )
        
        for grp_idx, group in enumerate(category.get('groups', [])):
            if not isinstance(group.get('layers', []), list):
                error(
                    severity='BLOCK',
                    rule='R7 Structure Integrity',
                    path=f'categories[{cat_idx}].groups[{grp_idx}].layers',
                    message='layers must be array',
                    suggested_fix='Convert to array: layers: [...]'
                )
    
    if not isinstance(registry.get('layers', {}), dict):
        error(
            severity='BLOCK',
            rule='R7 Structure Integrity',
            path='layers',
            message='layers must be a map/dict',
            suggested_fix='Convert to key-value dict: layers: { ... }'
        )
```

---

### Rule 8 — Phase 2 Service Contract (WMS-Only)

**Severity**: BLOCK

**Statement**: 
- Registry must declare WMS-only services for Phase 2.
- WFS definitions MUST NOT exist.
- `services.wms.allowed_requests` MUST equal `["GetCapabilities", "GetMap", "GetFeatureInfo"]`.

**Failure Examples**:
- `services.wfs` section present → BLOCK
- `services.wms.allowed_requests` includes `"GetFeature"` → BLOCK
- Missing `services.wms` entirely → BLOCK

**Validator Logic**:
```python
def check_phase2_service_contract(registry):
    services = registry.get('services', {})
    
    # WFS MUST NOT exist
    if 'wfs' in services:
        error(
            severity='BLOCK',
            rule='R8 Phase 2 Service Contract',
            path='services.wfs',
            message='WFS not permitted in Phase 2',
            suggested_fix='Remove services.wfs section'
        )
    
    # WMS MUST exist and be WMS-only
    if 'wms' not in services:
        error(
            severity='BLOCK',
            rule='R8 Phase 2 Service Contract',
            path='services',
            message='services.wms not defined',
            suggested_fix='Add services.wms section with allowed_requests'
        )
    else:
        wms = services['wms']
        allowed = wms.get('allowed_requests', [])
        expected = ["GetCapabilities", "GetMap", "GetFeatureInfo"]
        
        if set(allowed) != set(expected):
            error(
                severity='BLOCK',
                rule='R8 Phase 2 Service Contract',
                path='services.wms.allowed_requests',
                message=f'Expected {expected}, got {allowed}',
                suggested_fix=f'Set allowed_requests: {expected}'
            )
```

---

### Rule 9 — CRS Policy (Phase 2)

**Severity**: BLOCK

**Statement**:
- `atlas.canonical_crs` MUST equal `"EPSG:4326"` (frozen Phase 1 baseline)
- `atlas.view_crs` MUST equal `"EPSG:3857"` (Web Mercator for Phase 2)

**Failure Examples**:
- `canonical_crs: "EPSG:3857"` → BLOCK (storage CRS changed)
- `view_crs: "EPSG:4326"` → BLOCK (web map in lat/lon, inefficient)
- Missing either CRS key → BLOCK

**Validator Logic**:
```python
def check_crs_policy(registry):
    atlas = registry.get('atlas', {})
    
    canonical = atlas.get('canonical_crs')
    view = atlas.get('view_crs')
    
    if canonical != "EPSG:4326":
        error(
            severity='BLOCK',
            rule='R9 CRS Policy',
            path='atlas.canonical_crs',
            message=f'Expected EPSG:4326 (Phase 1 baseline), got {canonical}',
            suggested_fix='Set canonical_crs: "EPSG:4326"'
        )
    
    if view != "EPSG:3857":
        error(
            severity='BLOCK',
            rule='R9 CRS Policy',
            path='atlas.view_crs',
            message=f'Expected EPSG:3857 (Web Mercator for Phase 2), got {view}',
            suggested_fix='Set view_crs: "EPSG:3857"'
        )
```

---

## 5. Validator Output Specification

### 5.1 Console Output (Human-Readable)

Each issue printed with clear structure:

```
[BLOCK] R1 Referential Integrity
  Path: categories[0].groups[0].layers[2]
  Line: 42
  Message: Orphan layer reference: "ethiopia_kebeles" not found in layers map.
  Fix: Define layers.ethiopia_kebeles or remove reference from group list.

[WARN] R3 Publication Governance
  Path: layers.ethiopia_zones.attribution
  Line: 165
  Message: Placeholder text in attribution.
  Fix: Replace with actual data source credit.

---
Results: 1 BLOCK, 1 WARN
Validation: FAIL (1 BLOCK error)
Exit Code: 1
```

### 5.2 JSON Output (Machine-Readable)

Invoked with `--format json`:

```json
{
  "status": "FAIL",
  "error_count": 1,
  "warning_count": 1,
  "errors": [
    {
      "severity": "BLOCK",
      "rule_id": "R1",
      "rule_name": "Referential Integrity",
      "path": "categories[0].groups[0].layers[2]",
      "line": 42,
      "column": 4,
      "message": "Orphan layer reference: \"ethiopia_kebeles\" not found in layers map.",
      "suggested_fix": "Define layers.ethiopia_kebeles or remove reference from group list."
    }
  ],
  "warnings": [
    {
      "severity": "WARN",
      "rule_id": "R3",
      "rule_name": "Publication Governance",
      "path": "layers.ethiopia_zones.attribution",
      "line": 165,
      "column": 2,
      "message": "Placeholder text in attribution.",
      "suggested_fix": "Replace with actual data source credit."
    }
  ]
}
```

---

## 6. Validation Gates (Pre-Deployment)

Validation is enforced at multiple checkpoints:

### Gate A — Unit Tests (Mandatory)

Each rule (R1—R9) must have:
- **Positive test**: Valid registry input → PASS
- **Negative test**: Invalid input triggering rule → reports correct BLOCK/WARN

**Example**:
```python
def test_r1_orphan_reference():
    registry = load_yaml('test_orphan.yaml')  # Has invalid layer ref
    result = validate(registry)
    assert result.status == 'FAIL'
    assert any(e['rule_id'] == 'R1' for e in result.errors)

def test_r1_valid_references():
    registry = load_yaml('test_valid.yaml')  # All refs valid
    result = validate(registry)
    assert result.status == 'PASS' or (result.status == 'FAIL' and not any(e['rule_id'] == 'R1' for e in result.errors))
```

### Gate B — Integration Validation (Mandatory)

Validate complete real registry file as atomic unit:
- Load full `atlas-registry.yaml`
- All 9 rules must pass (0 BLOCK errors)
- Document baseline pass/fail signature

### Gate C — CI/CD Integration (Mandatory)

Validator runs on every commit/PR affecting:
- `atlas-registry.yaml`
- Validator source code itself
- Any mapfile changes (future cross-checks)

**Pipeline Step**:
```yaml
validate:
  script:
    - python validator.py docs/phase2/atlas-registry.yaml --format json
  allow_failure: false  # Block merge if validation fails
```

### Gate D — Pre-Commit Hook (Mandatory)

Block commits if BLOCK errors detected:

```bash
#!/bin/bash
# .git/hooks/pre-commit
validator docs/phase2/atlas-registry.yaml
if [ $? -ne 0 ]; then
    echo "Registry validation failed. Fix errors and retry."
    exit 1
fi
```

### Gate E — Manual Review (Mandatory Before Production)

Human checklist **before production deploy**:

- [ ] Validator reports: **0 BLOCK**, any WARNs explicitly approved
- [ ] Scale mutex pairs reviewed manually (visual plot/table check)
- [ ] Attribution fields free of placeholders (e.g., `"<to-fill>"`, `"TBD"`)
- [ ] WMS layer names spot-checked against MapServer mapfiles
- [ ] CRS values confirmed: 4326 canonical, 3857 view
- [ ] `search: []` confirmed intentional for Phase 2 scope
- [ ] Dual-scale layers verified distinct (roads, towns)

---

## 7. Deployment Checklist (Phase 2)

Before any Phase 2 registry deployment:

```
Pre-Deployment Validation Checklist
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❑ Validator PASS: 0 BLOCK errors, any WARNs approved
❑ Scale mutex pairs: manually verified non-overlapping ranges
❑ Attribution: all fields contain real data source (no placeholders)
❑ WMS names: spot-checked against MapServer mapfiles (tsird.map + includes)
❑ CRS values: canonical=EPSG:4326, view=EPSG:3857
❑ Search: intentionally empty (Phase 3 deferred)
❑ Health category: only tigray_health_facilities_2006 included
❑ Roads/Towns: dual-scale pairs with scale_mutex_pairs rules
❑ Credits: handled in UI shell (not a layer)
❑ Test coverage: all 9 rules tested (unit + integration)
❑ CI/CD gate: validator blocks PRs with errors
❑ Manual sign-off: code reviewer and project lead approval
```

---

## 8. Governance Notes (Beyond Validator)

### Published Immutability

Enforcement can be **process-based** or **tooling-based**:

**Option A (Process)**: Manual policy
- Require review for any change to `published: true` layers
- Document approval in commit message

**Option B (Tooling, optional future stage)**
- Maintain "state file" of released registry
- In CI, compare current registry to previous release tag
- Block changes to immutable fields (published status, wms_name)

**Phase 4 Scope**: Implement Option A (manual policy). Option B deferred to later.

---

## 9. Optional Enhancement (Future Stage)

### Mapfile Cross-Check (Stage 5+)

Parse MapServer mapfiles to verify declared WMS names:

**What it does**:
- Load `infra/mapserver/mapfiles/tsird.map` and includes
- Extract all `LAYER NAME "..."` definitions
- Verify every `layers[*].wms_name` in registry exists in mapfile

**Why it's strong**:
- Catches typos in wms_name values
- Ensures new layers in mapfile are registered before exposure

**Why it's optional now**:
- Adds parsing complexity (mapfile syntax is finicky)
- Registry validator is already comprehensive
- Can be retrofit in Stage 5 (MapServer Modularization)

**When to implement**: If mapfile changes become frequent or new layers are added.

---

## 10. Implementation Roadmap

**Phase 2 Scope (this stage)**:
1. [x] Define validator requirements
2. [x] Specify 9 constraint rules with logic
3. [x] Define output formats (console + JSON)
4. [x] Document validation gates (unit, integration, CI, pre-commit, manual)
5. ✓ Checklist ready for use

**Phase 2 Implementation (Stage 5 or parallel)**:
1. Write validator code (Python or Node.js)
2. Implement 9 rule checkers + unit tests
3. Integrate with CI/CD pipeline
4. Add pre-commit hook
5. Validate test registry

**Phase 3+ (Future)**:
1. Mapfile cross-check (optional enhancement)
2. State file comparison for published immutability (optional)
3. Performance optimization if registry grows large

---

**✓ END OF STAGE 4: VALIDATION POLICY FROZEN**

**Next Stage**: Stage 5 — MapServer Modularization (implement validation tool in parallel)
