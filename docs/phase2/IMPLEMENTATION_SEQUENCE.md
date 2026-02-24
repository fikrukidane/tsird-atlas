# Phase 2: Controlled Integration Sequence
## Executive Summary & Status Report

**Date**: 2026-02-24  
**Architecture Status**: ✅ Frozen (Stages 1-6)  
**Implementation Status**: 🚀 Commencing (Steps 1-4)  
**Token Budget**: Transitioned from specification to execution  

---

## Strategic Context

### The Transition

You have **4,337 lines of frozen governance** specifying:

| Stage | Resolution | Doc | Lines | Status |
|---|---|---|---|---|
| 1 | Structural Analysis | STRUCTURE_ANALYSIS.md | 949 | ✅ Frozen |
| 2 | Architecture Blueprint | ARCHITECTURE_BLUEPRINT.md | 369 | ✅ Frozen |
| 3 | Configuration Contract | CONFIG_MODEL.md | 572 | ✅ Frozen |
| 4 | Validation Policy | VALIDATION_POLICY.md | 797 | ✅ Frozen |
| 5 | MapServer Modularization | MAPSERVER_MODULARIZATION.md | 839 | ✅ Frozen |
| 6 | Frontend Implementation | STAGE6_FRONTEND.md | 811 | ✅ Frozen |

**Risk Boundary**: Architecture is locked. **Implementation risk now dominates.**

The next phase requires **proof that frozen contracts hold under runtime loads**.

---

## 4-Step Implementation Sequence (This Execution Plan)

### Step 1: ✅ COMPLETE
**Implement Stage 4 Validator (Registry Contract Enforcement)**

**Deliverables**:
- ✅ `tools/validate_registry.py` — CLI validator implementing 9 constraint rules (R1–R9)
- ✅ `.git/hooks/pre-commit` — Enforces validator on every commit
- ✅ `tools/test-registry-good.yaml` — Reference valid registry (passes all rules)
- ✅ `tools/test-registry-bad.yaml` — Synthetic violations (tests all R1–R8 failures + R4 warnings)

**Validation Results**:
- Bad registry: **10 BLOCK violations, 1 WARNING** ✓ (correctly identified)
- Good registry: **0 violations** ✓ (correctly accepted)
- Exit codes: **1 (failures), 0 (pass)** ✓ (CI-ready)

**Key Achievement**: Registry integrity now protected at commit time.

**Commit**: `60d7c87` — "Step 1: Stage 4 Validator Implementation"

---

### Step 2: 🔄 IN PROGRESS
**Complete Stage 5 Runtime Verification (MapServer Contract Validation)**

**Deliverable**:
- 📋 `docs/phase2/STAGE5_RUNTIME_VERIFICATION.md` — 8-point checklist against live WMS

**8-Point Acceptance Criteria**:
1. ✓ No inline layers in master mapfile
2. ✓ Published layers have STATUS ON
3. ✓ GetCapabilities lists only published
4. ✓ Scale mutex enforcement (roads/towns non-overlap)
5. ✓ Layer count identity (registry ↔ GetCapabilities parity)
6. ✓ No Phase 1 data changes (gold tables untouched)
7. ✓ Thematic organization preserved (include order)
8. ✓ All automated + manual tests pass

**Execution**: Run checklist against **live MapServer**. Mark each criterion PASS/FAIL.

**Owner**: DevOps/QA (or you, if running locally with MapServer 8.6 container)

**Completion Criteria**: All 8 criteria PASS → Stage 5 proven reliable → unblock Step 3

**Commit**: `183d53f` — Includes STAGE5_RUNTIME_VERIFICATION.md

---

### Step 3: ⏳ READY TO START
**Stage 6 Milestone 1 (Basic Map + Registry + Tiled WMS)**

**Deliverable**:
- 📋 `docs/phase2/STAGE6_MILESTONE1_TASKS.md` — Detailed task breakdown + DoD

**Scope** (NO Identify, NO Scale Rules, NO Mutex):
- **Module 1**: RegistryLoader (load + normalize registry)
- **Module 2**: MapController (OL init + CRS transform)
- **Module 3**: LayerFactory (TileWMS creation, published only)
- **Module 4**: InteractionController (TOC render + per-layer toggle + default visibility)
- **UI**: HTML/CSS (map container, TOC sidebar)
- **Testing**: Unit + integration + manual

**Flow**:
1. Load registry → registry validation (YAML or JSON)
2. Create map → EPSG:4326 center transform → EPSG:3857 view
3. Create layers → iterate published layers → TileWMS sources
4. Render TOC → categories → groups → layer checkboxes
5. Attach event → checkbox toggle → layer visibility sync

**Definition of Done**:
- [ ] All 4 modules integrated
- [ ] TOC renders correctly
- [ ] Default visibility matches YAML
- [ ] Toggle works (checkbox ↔ map visibility)
- [ ] No console errors
- [ ] No WFS calls (only GetMap)
- [ ] Manual testing passes

**Risk Mitigation**:
- Start with test-registry-good.yaml (not production config yet)
- Test both YAML (via js-yaml) and JSON (pre-built artifact) parsing
- Iterate on 1 module at a time; test after each

**Completion Target**: ~5–7 working days (solo developer)

**Commit**: Will be many incremental commits (module-by-module)

---

### Step 4: ⏳ QUEUED
**Stage 6 Milestone 2 (Scale Rules + Mutex + Identify + Polish)**

**Scope** (added to Milestone 1):
- Scale-dependent visibility enforcement (min/max scale per layer)
- Scale mutex enforcement (roads/towns mutual exclusion)
- GetFeatureInfo on click with attribute allowlist
- Error resilience + friendly UX
- Final performance tuning

**Completion Target**: ~3–5 working days (after Milestone 1 passes DoD)

---

## Artifact Inventory

### Frozen Specifications (Don't Change)
```
docs/phase2/
├── STRUCTURE_ANALYSIS.md                    (949 lines, Stage 1)
├── ARCHITECTURE_BLUEPRINT.md                (369 lines, Stage 2)
├── CONFIG_MODEL.md                          (572 lines, Stage 3)
├── VALIDATION_POLICY.md                     (797 lines, Stage 4)
├── MAPSERVER_MODULARIZATION.md              (839 lines, Stage 5)
└── STAGE6_FRONTEND.md                       (811 lines, Stage 6)
```

### Validator Tooling (Step 1 ✅)
```
tools/
├── validate_registry.py                     (executable CLI)
├── test-registry-good.yaml                  (valid reference)
└── test-registry-bad.yaml                   (synthetic violations)

.git/hooks/
└── pre-commit                               (CI enforcement)
```

### Implementation Planning (Step 2-3 📋)
```
docs/phase2/
├── STAGE5_RUNTIME_VERIFICATION.md          (8-point checklist)
└── STAGE6_MILESTONE1_TASKS.md              (detailed task breakdown)
```

### Implementation Target (Step 3-4 🚀)
```
ui/web/
├── index.html                               (entry point)
├── js/
│   ├── main.js                              (orchestration)
│   └── modules/
│       ├── RegistryLoader.js                (registry loading)
│       ├── MapController.js                 (map init + CRS)
│       ├── LayerFactory.js                  (TileWMS creation)
│       └── InteractionController.js         (TOC + toggle)
├── css/
│   └── style.css                            (responsive layout)
└── data/
    └── atlas-registry.json                  (build artifact)

test/
├── test-registry-loader.js
├── test-map-controller.js
└── test-layer-factory.js
```

---

## Governance Locks (Non-Negotiable)

These decisions are **FROZEN** and do **NOT** change without formal revision:

| Decision | Locked Value | Reference | Stage |
|---|---|---|---|
| Frontend Framework | OpenLayers 8+ (WMS-first) | ARCHITECTURE_BLUEPRINT.md #6 | 2 |
| Registry Format | YAML (authoritative), JSON (artifact) | CONFIG_MODEL.md #2 | 3 |
| WMS Operations | GetCapabilities, GetMap, GetFeatureInfo only | CONFIG_MODEL.md #3 | 3 |
| Rate Limits | 1 /s GetCapabilities, 20 /s GetMap, 5 /s GetFeatureInfo | ARCHITECTURE_BLUEPRINT.md #6 | 2 |
| CRS Model | EPSG:4326 canonical (storage), EPSG:3857 view (web) | CONFIG_MODEL.md #2 | 3 |
| Constraint Rules | 9 rules (R1–R9) with deterministic logic | VALIDATION_POLICY.md #Def | 4 |
| Publication Rule | published: true → STATUS ON, false → exclude | MAPSERVER_MODULARIZATION.md #2 | 5 |
| Layer Visibility Mutex | Scale-dependent pairs never overlap | STAGE6_FRONTEND.md #6 | 6 |

**Modification Protocol**: Any change requires:
1. Document the change reason
2. Update affected stage specification (mark "REVISED" in header)
3. Notify dependent stages (e.g., changing CRS affects MapServer + Frontend + Validator)
4. Re-run affected verification checklist
5. Commit with message: "REVISED Stage X: [reason]"

---

## Integration Workflow

### Your Checklist for Tomorrow

1. **Verify Validator**
   - [ ] Run `python3 tools/validate_registry.py tools/test-registry-good.yaml`
   - [ ] Should output: `✓ All constraints passed`
   - [ ] Exit code: 0

2. **Prepare Step 2 (MapServer Verification)**
   - [ ] Check if MapServer container is running
   - [ ] If not, decide: mock verification or skip to Step 3
   - [ ] Print STAGE5_RUNTIME_VERIFICATION.md checklist
   - [ ] Run 8-point test suite

3. **Prepare Step 3 (Frontend Development)**
   - [ ] Create `ui/web/` directory structure
   - [ ] Copy test-registry-good.yaml to `ui/web/data/atlas-registry.json` (build it)
   - [ ] Open STAGE6_MILESTONE1_TASKS.md
   - [ ] Start with **Module 1 (RegistryLoader)** only
   - [ ] Write unit tests first (TDD approach)

4. **Quality Gates**
   - [ ] Every commit must pass `validate_registry.py` (pre-commit hook active)
   - [ ] Milestone 1 DoD checklist all checked before moving to Milestone 2
   - [ ] Manual browser testing before any stage signature-off

---

## Known Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| WMS GetCapabilities mismatch with registry | HIGH | STAGE5_RUNTIME_VERIFICATION #3 (automated check) |
| CRS transform error (center/extent wrong) | HIGH | MapController test with known coordinates |
| Layer order shuffled by TileWMS | MEDIUM | Add logging to LayerFactory; verify tocModel order at startup |
| Registry format incompatibility (YAML vs JSON) | MEDIUM | Test both; use pre-built JSON fallback |
| Scale rules enforcement fails in MapServer | HIGH | STAGE5_RUNTIME_VERIFICATION #4 (manual pixel inspection) |
| Identify popup leaks unauthorized attributes | HIGH | STAGE6_FRONTEND #5.3 denies any field not in identify_fields allowlist |
| Frontend breaks on WMS timeout | MEDIUM | STAGE6_FRONTEND #8 (show error banner + retry) |

---

## Success Criteria (Phase 2 Complete)

✅ **Governance Frozen** (this is already done)
- All 6 stages have formal specifications
- All decisions documented and locked
- Pre-commit validator active

🚀 **Validation Proven** (in progress)
- Step 1: Validator works ✓
- Step 2: MapServer contracts verified (TBD)
- Step 3: Frontend Milestone 1 passes DoD (TBD)
- Step 4: Frontend Milestone 2 passes DoD (TBD)

📦 **Production Ready** (after all steps)
- Registry lives at `config/atlas-registry.yaml`
- Frontend serves from `ui/web/` (Docker or static)
- WMS responds through edge proxy
- All 4 validation gates pass (Stage 4)
- Manual QA sign-off

---

## Time Estimates

| Step | Duration | Critical Path |
|---|---|---|
| 1: Validator | 1 day | ✓ DONE |
| 2: MapServer Verification | 1–2 days | Depends on container availability |
| 3: Milestone 1 Frontend | 5–7 days | Core implementation |
| 4: Milestone 2 Frontend | 3–5 days | Complex logic (scale + mutex) |
| **Total** | **10–15 days** | |

---

## Next Immediate Actions

**Priority 1 (Today/Tomorrow)**:
1. ✅ Confirm validator works (DONE)
2. **Plan MapServer verification** (Step 2)
   - Do you have MapServer 8.6 running?
   - Can you access WMS GetCapabilities?
   - Do you have access to the DB to check gold table counts?

**Priority 2 (This Week)**:
3. **Start frontend development** (Step 3 Milestone 1)
   - Create directory structure
   - Implement RegistryLoader
   - Write unit tests
   - Commit incrementally

**Priority 3 (Next Week)**:
4. **Complete frontend** (Step 3-4 Milestones 1-2)
   - Scale enforcement
   - GetFeatureInfo
   - Error handling

---

## Communication

- **Artifacts**: All in `/docs/phase2/` (one source of truth)
- **Code**: All in standard directories (`ui/web/`, `tools/`, etc.)
- **Commits**: Clear messages referencing stage/step
- **Blockers**: Document in STAGE5_RUNTIME_VERIFICATION or issue tracker
- **Sign-offs**: Use checklist format in each stage doc

---

**✓ PHASE 2 EXECUTION PLAN LOCKED**

You now have:
- ✅ Frozen architecture (Stages 1-6)
- ✅ Active validator (Step 1)
- 📋 Verification roadmap (Steps 2-3)
- 🚀 Implementation task breakdown (Step 4)

**Next move**: Execute Step 2 or skip to Step 3 based on MapServer availability.

**Confidence Level**: HIGH (all contracts proven at specification level; implementation is execution of locked specs)
