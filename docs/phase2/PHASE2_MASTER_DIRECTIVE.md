TSIRD Phase 2 — Master Implementation Directive
Public Web Atlas – Presentation Layer

Date Context: February 22, 2026

🔒 PHASE 1 BASELINE CLARIFICATION (MANDATORY CONTEXT)

Phase 1 has already been completed and is operational.

The following components exist and must be treated as the foundation:

Dockerized MapServer (serving WMS/WFS)

PostGIS database

Gold datasets (EPSG:4326)

Existing MapServer mapfiles configured to read Gold layers

Working WMS services

Phase 2 must:

Build on top of this existing infrastructure.

Not recreate MapServer from scratch.

Not regenerate mapfiles from legacy XML.

Not redesign the database.

Only reorganize, modularize, and extend presentation behavior.

Legacy configuration artifacts are reference material only.

The backend stack is already built.

0. OBJECTIVE

Build a modern, professional, publicly accessible web atlas for:

Ethiopia (national context)

Tigray (regional focus)

The system must:

Use existing MapServer backend.

Be fully Dockerized.

Be HTTPS-ready.

Be configuration-driven.

Be secure.

Be extensible.

Support future dataset expansion without frontend refactoring.

Be fully documented.

1. FINAL PRODUCT DEFINITION
1.1 Default Load State

On first load:

Projection: EPSG:3857.

Map centered on Tigray.

Default visible layers:

Roads

DEM or hillshade.

Clean UI including:

Layer tree (categories → groups → layers)

Identify tool

Structured search

Legend panel.

1.2 Functional Capabilities

Category-based grouping.

Group toggles.

Scale-dependent visibility.

Click-to-identify.

Structured search (dropdown, text-like, numeric compare).

Highlight of selected features.

Controlled WFS exposure.

No console errors.

Smooth interaction.

2. GLOBAL NON-NEGOTIABLE RULES

Phase 2 must not modify Phase 1 data engineering.

MapServer reads only Gold layers.

Internal CRS remains EPSG:4326.

UI configuration is the authoritative behavior specification.

No hardcoded layer logic in frontend.

No assumptions about structure.

Every stage must produce documentation.

Each stage must be committed independently.

New datasets must not require frontend code changes.

3. CONFIGURATION INPUT GATE (MANDATORY)

Before defining taxonomy or behavior:

VS Code AI must:

Ask the user to provide configuration artifacts (XML and/or YAML) that represent the intended atlas structure.

Clarify these are needed to understand:

Category hierarchy

Grouping logic

Default visibility behavior

Search expectations

Naming conventions

Pause until artifacts are provided.

Perform structural extraction only.

Document findings.

Do not fabricate taxonomy.

Do not infer missing structure.

No structural decisions before review.

4. STAGE 1 — STRUCTURAL ANALYSIS
Deliverable

docs/phase2/STRUCTURE_ANALYSIS.md

Must include:

Extracted categories

Extracted groups

Extracted layers

Default visibility behavior

Search definitions

Query/identify settings

Naming conventions

Mismatch analysis

Structural risks

Recommendations (no implementation)

Approval required before proceeding.

5. STAGE 2 — ARCHITECTURE FREEZE
Deliverable

docs/phase2/ARCHITECTURE_BLUEPRINT.md

Must define:

Browser → HTTPS Reverse Proxy → MapServer → PostGIS

Clear separation of responsibilities

Data flow

Interaction flow

Security boundary

Future MapCache insertion point

Approval required.

6. STAGE 3 — CONFIGURATION CONTRACT DESIGN
Deliverable

docs/phase2/CONFIG_MODEL.md

Must define:

Taxonomy (categories → groups → layers)

Startup defaults

Scale behavior

Identify contract

Search contract

Legend policy

Scope separation

Must specify:

Required keys

Optional keys

Referential rules

Validation expectations

All behavior config-driven.

7. STAGE 4 — CONFIG VALIDATION POLICY
Deliverable

docs/phase2/CONFIG_VALIDATION_POLICY.md

Validator must ensure:

No orphan groups

No missing layers

No duplicate IDs

Valid search references

Valid identify allowlist

No unknown keys

Failure blocks deployment.

8. STAGE 5 — MAPSERVER MODULARIZATION
Reinforcement of Baseline

MapServer already exists and works.

This stage reorganizes existing configuration only.

It does NOT:

Rebuild MapServer

Regenerate from XML

Redesign database

Deliverable

docs/phase2/MAPSERVER_STRUCTURE.md

Rules:

One master mapfile.

Include-based structure.

One layer per file.

Centralized styles.

Scale rules enforced.

Attribute exposure controlled.

9. STAGE 6 — FRONTEND IMPLEMENTATION
Deliverable

docs/phase2/FRONTEND_ARCHITECTURE.md

Requirements:

TOC built from config.

Startup defaults applied.

WMS-first rendering.

Identify via WMS.

Popup templates config-driven.

Scale disabling visible.

No hardcoded layer names.

10. STAGE 7 — STRUCTURED SEARCH
Deliverable

docs/phase2/SEARCH_MODEL.md

Requirements:

Typed search only.

Layer allowlist.

Result limit enforced.

Highlight result.

No arbitrary attribute exposure.

11. STAGE 8 — SECURITY HARDENING
Deliverable

docs/phase2/SECURITY_MODEL.md

Must include:

HTTPS readiness.

Reverse proxy enforcement.

Rate limiting.

WFS restriction.

No direct DB exposure.

12. STAGE 9 — PERFORMANCE BASELINE
Deliverable

docs/phase2/PERFORMANCE_ROADMAP.md

Baseline:

WMS-first.

Controlled identify size.

Scale-limited labels.

Future-ready for MapCache.

13. STAGE 10 — DATASET EXPANSION PROTOCOL

The atlas must support new datasets without structural refactoring.

Whenever new datasets are ingested:

Ensure Gold layer integrity (Phase 1).

Register layer in MapServer modular file.

Register layer in configuration.

Update taxonomy if needed.

Run validation.

Validate service endpoints.

Confirm TOC auto-render.

Confirm identify/search behavior.

Commit.

No frontend code changes allowed for onboarding.

Groups must be stable and generic enough to absorb future datasets.

Versioning strategy must be documented.

14. STRICT EXECUTION ORDER

Configuration Input Gate

Structural Analysis

Architecture Freeze

Config Contract Design

Validation Policy

MapServer Modularization

Frontend MVP

Identify

Search

Security

Performance

Dataset Expansion Protocol

Documentation consolidation

No parallelization.
No skipping.
No assumption-based design.

15. COMPLETION CRITERIA

Phase 2 is complete when:

Atlas loads centered on Tigray.

Roads + DEM visible.

Layer tree functional.

Identify works.

Search works.

Legend correct.

No console errors.

Config validation passes.

Docker deployment reproducible.

Documentation complete.

New datasets can be onboarded without frontend modification.
