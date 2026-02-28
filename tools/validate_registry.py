#!/usr/bin/env python3
"""
TSIRD Phase 2 - Stage 4 Registry Validator

Validates atlas-registry.yaml against 9 constraint rules (R1-R9).

Usage:
  python validate_registry.py <registry_path> [--format=text|json] [--strict]

Exit Codes:
  0 = All BLOCK rules pass (warnings allowed)
  1 = At least one BLOCK rule failed
  2 = Registry file not found or malformed

With --strict: warnings treated as failures (exit 1)
"""

import sys
import json
import argparse
import yaml
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Set, Tuple


@dataclass
class Violation:
    """Single constraint violation."""
    rule_id: str  # R1, R2, ..., R9
    severity: str  # "BLOCK" or "WARN"
    message: str
    layer_id: str = None
    layer_wms_name: str = None


class RegistryValidator:
    """Validates registry against Stage 4 rules."""

    def __init__(self, registry_path: str):
        self.registry_path = Path(registry_path)
        self.registry = None
        self.violations: List[Violation] = []
        self._load_registry()

    def _load_registry(self):
        """Load and parse YAML registry."""
        try:
            with open(self.registry_path, 'r') as f:
                self.registry = yaml.safe_load(f)
            if self.registry is None:
                raise ValueError("Registry is empty or invalid YAML")
        except FileNotFoundError:
            raise FileNotFoundError(f"Registry not found: {self.registry_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")

    def validate(self) -> bool:
        """Run all 9 constraint rules. Return True if all BLOCK rules pass."""
        self.violations = []
        
        self._rule_1_referential_integrity()
        self._rule_2_unique_wms_names()
        self._rule_3_publication_governance()
        self._rule_4_query_rules()
        self._rule_5_scale_convention()
        self._rule_6_scale_mutex()
        self._rule_7_structure_integrity()
        self._rule_8_service_contract()
        self._rule_9_crs_policy()
        
        # Return True if no BLOCK violations
        return not any(v.severity == "BLOCK" for v in self.violations)

    def _rule_1_referential_integrity(self):
        """R1: No orphan layers in scale_mutex_pairs."""
        if not self.registry or 'rules' not in self.registry:
            return
        
        rules = self.registry.get('rules', {})
        mutex_pairs = rules.get('scale_mutex_pairs', [])
        all_layer_ids = self._get_all_layer_ids()
        
        for pair in mutex_pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                self.violations.append(Violation(
                    rule_id="R1",
                    severity="BLOCK",
                    message=f"scale_mutex_pairs entry is not a 2-element list: {pair}"
                ))
                continue
            
            for layer_id in pair:
                if layer_id not in all_layer_ids:
                    self.violations.append(Violation(
                        rule_id="R1",
                        severity="BLOCK",
                        message=f"scale_mutex_pairs references undefined layer: {layer_id}",
                        layer_id=layer_id
                    ))

    def _rule_2_unique_wms_names(self):
        """R2: WMS layer names must be unique. Basemaps (base_layer=true) exempt from wms_name requirement."""
        wms_names: Dict[str, str] = {}
        
        for layer in self._iter_layers():
            # Basemaps with source_type xyz don't need wms_name
            if layer.get('base_layer') and layer.get('source_type') == 'xyz':
                # Validate basemap has required fields instead
                if not layer.get('url_template'):
                    self.violations.append(Violation(
                        rule_id="R2",
                        severity="BLOCK",
                        message=f"Basemap missing url_template",
                        layer_id=layer.get('id')
                    ))
                continue
            
            wms_name = layer.get('wms_name')
            if not wms_name:
                self.violations.append(Violation(
                    rule_id="R2",
                    severity="BLOCK",
                    message=f"Layer missing wms_name",
                    layer_id=layer.get('id')
                ))
                continue
            
            if wms_name in wms_names:
                self.violations.append(Violation(
                    rule_id="R2",
                    severity="BLOCK",
                    message=f"Duplicate wms_name: {wms_name} (layers: {wms_names[wms_name]}, {layer.get('id')})",
                    layer_wms_name=wms_name
                ))
            else:
                wms_names[wms_name] = layer.get('id')

    def _rule_3_publication_governance(self):
        """R3: published flag immutability enforcement (structural check only)."""
        for layer in self._iter_layers():
            published = layer.get('published')
            if published is None:
                self.violations.append(Violation(
                    rule_id="R3",
                    severity="BLOCK",
                    message="Layer missing 'published' key",
                    layer_id=layer.get('id')
                ))
            elif not isinstance(published, bool):
                self.violations.append(Violation(
                    rule_id="R3",
                    severity="BLOCK",
                    message=f"published must be boolean, got {type(published).__name__}",
                    layer_id=layer.get('id')
                ))

    def _rule_4_query_rules(self):
        """R4: queryable ↔ identify_fields consistency."""
        for layer in self._iter_layers():
            queryable = layer.get('queryable', False)
            identify_fields = layer.get('identify_fields', [])
            
            if queryable and not identify_fields:
                self.violations.append(Violation(
                    rule_id="R4",
                    severity="BLOCK",
                    message="queryable=true but identify_fields is empty",
                    layer_id=layer.get('id')
                ))
            
            if not queryable and identify_fields:
                self.violations.append(Violation(
                    rule_id="R4",
                    severity="WARN",
                    message="queryable=false but identify_fields is non-empty (unreachable)",
                    layer_id=layer.get('id')
                ))

    def _rule_5_scale_convention(self):
        """R5: min_scale > max_scale, positive integers."""
        for layer in self._iter_layers():
            min_scale = layer.get('min_scale')
            max_scale = layer.get('max_scale')
            
            # Scale rules are optional; if present, must be valid
            if min_scale is not None:
                if not isinstance(min_scale, int) or min_scale <= 0:
                    self.violations.append(Violation(
                        rule_id="R5",
                        severity="BLOCK",
                        message=f"min_scale must be positive integer, got {min_scale}",
                        layer_id=layer.get('id')
                    ))
            
            if max_scale is not None:
                if not isinstance(max_scale, int) or max_scale <= 0:
                    self.violations.append(Violation(
                        rule_id="R5",
                        severity="BLOCK",
                        message=f"max_scale must be positive integer, got {max_scale}",
                        layer_id=layer.get('id')
                    ))
            
            # If both present: min_scale must be > max_scale (cartographic convention)
            if min_scale is not None and max_scale is not None:
                if min_scale <= max_scale:
                    self.violations.append(Violation(
                        rule_id="R5",
                        severity="BLOCK",
                        message=f"min_scale ({min_scale}) must be > max_scale ({max_scale})",
                        layer_id=layer.get('id')
                    ))

    def _rule_6_scale_mutex(self):
        """R6: scale_mutex_pairs do not overlap."""
        if not self.registry or 'rules' not in self.registry:
            return
        
        rules = self.registry.get('rules', {})
        mutex_pairs = rules.get('scale_mutex_pairs', [])
        layer_defs = {layer.get('id'): layer for layer in self._iter_layers()}
        
        for pair_idx, pair in enumerate(mutex_pairs):
            if len(pair) != 2:
                continue  # Already caught by R1
            
            layer_a_id, layer_b_id = pair
            layer_a = layer_defs.get(layer_a_id)
            layer_b = layer_defs.get(layer_b_id)
            
            if not layer_a or not layer_b:
                continue  # Already caught by R1
            
            # Check for scale overlap
            a_min, a_max = layer_a.get('min_scale'), layer_a.get('max_scale')
            b_min, b_max = layer_b.get('min_scale'), layer_b.get('max_scale')
            
            # Both must have scale rules to be in a mutex pair
            if (a_min is None or a_max is None or b_min is None or b_max is None):
                self.violations.append(Violation(
                    rule_id="R6",
                    severity="BLOCK",
                    message=f"Mutex pair [{layer_a_id}, {layer_b_id}]: both layers must have min_scale and max_scale",
                    layer_id=layer_a_id
                ))
                continue
            
            # Check overlap: [a_min, a_max] vs [b_min, b_max]
            # Cartographic convention: max < min (e.g., 500k < 50M)
            # Overlap if: NOT (a_min < b_max OR b_min < a_max)
            if not (a_min < b_max or b_min < a_max):
                self.violations.append(Violation(
                    rule_id="R6",
                    severity="BLOCK",
                    message=f"Mutex pair scale overlap: {layer_a_id} [{a_max},{a_min}] vs {layer_b_id} [{b_max},{b_min}]",
                    layer_id=layer_a_id
                ))

    def _rule_7_structure_integrity(self):
        """R7: categories → groups → layers hierarchy must be valid."""
        if not self.registry:
            return
        
        if 'categories' not in self.registry:
            self.violations.append(Violation(
                rule_id="R7",
                severity="BLOCK",
                message="Missing 'categories' key in registry"
            ))
            return
        
        categories = self.registry.get('categories', [])
        if not isinstance(categories, list):
            self.violations.append(Violation(
                rule_id="R7",
                severity="BLOCK",
                message=f"'categories' must be a list, got {type(categories).__name__}"
            ))
            return
        
        for cat_idx, category in enumerate(categories):
            if not isinstance(category, dict):
                self.violations.append(Violation(
                    rule_id="R7",
                    severity="BLOCK",
                    message=f"categories[{cat_idx}] is not a dict"
                ))
                continue
            
            if 'groups' not in category:
                self.violations.append(Violation(
                    rule_id="R7",
                    severity="BLOCK",
                    message=f"Category {category.get('id')} is missing 'groups' key"
                ))
                continue
            
            groups = category.get('groups', [])
            if not isinstance(groups, list):
                self.violations.append(Violation(
                    rule_id="R7",
                    severity="BLOCK",
                    message=f"Category {category.get('id')}: 'groups' must be a list"
                ))
                continue
            
            for grp_idx, group in enumerate(groups):
                if not isinstance(group, dict):
                    self.violations.append(Violation(
                        rule_id="R7",
                        severity="BLOCK",
                        message=f"categories[{cat_idx}].groups[{grp_idx}] is not a dict"
                    ))
                    continue
                
                if 'layers' not in group:
                    self.violations.append(Violation(
                        rule_id="R7",
                        severity="BLOCK",
                        message=f"Group {group.get('id')} is missing 'layers' key"
                    ))
                    continue
                
                layers = group.get('layers', [])
                if not isinstance(layers, list):
                    self.violations.append(Violation(
                        rule_id="R7",
                        severity="BLOCK",
                        message=f"Group {group.get('id')}: 'layers' must be a list"
                    ))

    def _rule_8_service_contract(self):
        """R8: Phase 2 service contract (WMS-only, no WFS)."""
        if not self.registry or 'services' not in self.registry:
            self.violations.append(Violation(
                rule_id="R8",
                severity="BLOCK",
                message="Missing 'services' key in registry"
            ))
            return
        
        services = self.registry.get('services', {})
        wms = services.get('wms')
        
        if not wms:
            self.violations.append(Violation(
                rule_id="R8",
                severity="BLOCK",
                message="services.wms is missing"
            ))
            return
        
        allowed_requests = wms.get('allowed_requests', [])
        if not isinstance(allowed_requests, list):
            self.violations.append(Violation(
                rule_id="R8",
                severity="BLOCK",
                message="services.wms.allowed_requests must be a list"
            ))
            return
        
        # Phase 2: only GetCapabilities, GetMap, GetFeatureInfo allowed
        allowed_set = set(allowed_requests)
        required_set = {"GetCapabilities", "GetMap", "GetFeatureInfo"}
        forbidden_set = {"GetFeature", "GetPropertyValue"}  # WFS operations
        
        if not required_set.issubset(allowed_set):
            missing = required_set - allowed_set
            self.violations.append(Violation(
                rule_id="R8",
                severity="BLOCK",
                message=f"Phase 2 requires WMS operations: {missing} missing"
            ))
        
        forbidden_found = forbidden_set & allowed_set
        if forbidden_found:
            self.violations.append(Violation(
                rule_id="R8",
                severity="BLOCK",
                message=f"Phase 2 forbids WFS operations: {forbidden_found} found"
            ))

    def _rule_9_crs_policy(self):
        """R9: CRS policy (EPSG:4326 canonical, EPSG:3857 view)."""
        if not self.registry or 'atlas' not in self.registry:
            self.violations.append(Violation(
                rule_id="R9",
                severity="BLOCK",
                message="Missing 'atlas' key in registry"
            ))
            return
        
        atlas = self.registry.get('atlas', {})
        
        canonical = atlas.get('canonical_crs')
        view = atlas.get('view_crs')
        
        if canonical != "EPSG:4326":
            self.violations.append(Violation(
                rule_id="R9",
                severity="BLOCK",
                message=f"canonical_crs must be EPSG:4326, got {canonical}"
            ))
        
        if view != "EPSG:3857":
            self.violations.append(Violation(
                rule_id="R9",
                severity="BLOCK",
                message=f"view_crs must be EPSG:3857, got {view}"
            ))

    def _iter_layers(self):
        """Iterate over all layer objects from top-level layers dict (frozen schema)."""
        if not self.registry:
            return
        
        # Frozen schema: layers are in top-level 'layers' dictionary
        layers_dict = self.registry.get('layers', {})
        for layer_id, layer_meta in layers_dict.items():
            # Add 'id' field for consistency with validators
            layer_obj = dict(layer_meta)
            layer_obj['id'] = layer_id
            yield layer_obj

    def _get_all_layer_ids(self) -> Set[str]:
        """Return set of all layer IDs from top-level layers dict."""
        if not self.registry:
            return set()
        return set(self.registry.get('layers', {}).keys())

    def format_text(self) -> str:
        """Format violations as human-readable text."""
        if not self.violations:
            return "✓ All constraints passed\n"
        
        blocks = [v for v in self.violations if v.severity == "BLOCK"]
        warns = [v for v in self.violations if v.severity == "WARN"]
        
        lines = []
        
        if blocks:
            lines.append(f"❌ BLOCK ({len(blocks)} failures):")
            for v in blocks:
                layer_info = f" [{v.layer_id}]" if v.layer_id else ""
                lines.append(f"  {v.rule_id}: {v.message}{layer_info}")
        
        if warns:
            lines.append(f"\n⚠️  WARN ({len(warns)} warnings):")
            for v in warns:
                layer_info = f" [{v.layer_id}]" if v.layer_id else ""
                lines.append(f"  {v.rule_id}: {v.message}{layer_info}")
        
        return "\n".join(lines) + "\n"

    def format_json(self) -> str:
        """Format violations as JSON."""
        return json.dumps({
            "valid": not any(v.severity == "BLOCK" for v in self.violations),
            "blocks": len([v for v in self.violations if v.severity == "BLOCK"]),
            "warns": len([v for v in self.violations if v.severity == "WARN"]),
            "violations": [asdict(v) for v in self.violations]
        }, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Validate TSIRD Phase 2 registry against Stage 4 constraints"
    )
    parser.add_argument("registry", help="Path to atlas-registry.yaml")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as failures")
    
    args = parser.parse_args()
    
    try:
        validator = RegistryValidator(args.registry)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    
    valid = validator.validate()
    
    if args.format == "json":
        print(validator.format_json())
    else:
        print(validator.format_text(), end="")
    
    if args.strict:
        has_warns = any(v.severity == "WARN" for v in validator.violations)
        if not valid or has_warns:
            sys.exit(1)
    else:
        if not valid:
            sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
