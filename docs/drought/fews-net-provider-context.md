# FEWS NET provider-context integration

## Purpose

FEWS NET is an external, attributed food-security evidence source for TSIRD.
It can provide a valuable independent context and validation lens for drought
planning. It does **not** provide a basis for an Atlas-generated food-security
classification, an IPC determination, assistance eligibility, or automatic
Tabia priority scoring.

The initial scope is Ethiopia acute food-insecurity classification products at
their provider-issued Food Security Classification (FSC) geography. FSC units
can be administrative units, livelihood zones, or their intersections; they
are not assumed to match a TSIRD Woreda or Tabia.

## Public products reviewed

| Product | Potential TSIRD role | Initial handling |
| --- | --- | --- |
| Acute food-insecurity classifications | Current, near-term, medium-term provider context | First candidate for a native-FSC GIS layer. |
| Acutely food-insecure population estimates | Context for the provider's FSC units | Review after classification geography is established. |
| FSC mapping units and administrative boundaries | Native geometry and time-aware unit definition | Retain with the matching classification issue. |
| Market prices | Purchasing-power and market-pressure context | Separate series-specific contract; no composite score. |
| Cross-border trade | Regional supply context | Later, separate country/route contract. |
| Livelihood zones, seasonal calendars and HEA data | Seasonal interpretation and model research | Later, permission-aware review; never use restricted data without access approval. |
| Production, nutrition, relief and demographic series | Possible supporting context | Catalogue and evaluate per data-use policy; not assumed public. |

## Retained historical context

The local development loader has retained the official Ethiopia native-FSC
GeoJSON issues available for **January, February, April, June and July 2026**.
Each retained issue records its reporting date, source URL, raw provider
properties and native geometry. In the Priority workspace, a user can select
one issue and show it separately or as an outline comparison with the local
historical replay.

When a Tabia is selected, TSIRD reports only the provider-native FSC areas
that intersect it, including the raw provider value, scenario and projection
dates. This is a spatial comparison, not a crosswalk: no classification is
transferred or downscaled to the Tabia.

`fews_net_public_classification_discovery.py` remains the controlled public
catalogue check for future releases. The earlier FDW ML1 one-record probe was
replaced because repeated provider timeouts made it unsuitable as the first
public-access gate.

## Required approval before a loader

A reviewer must select a single official provider issue and record:

1. provider publication URL and asset URL;
2. issue/collection date, current/near-term/medium-term validity dates, and
   scenario;
3. declared data-use policy, citation and redistribution conditions;
4. asset format, CRS, schema, geometry count and whether it is an FSC unit;
5. a source-time run ID and checksum; and
6. the presentation label: `FEWS NET provider context — native FSC geography`.

Only then may a bounded downloader retain the selected asset. A future
crosswalk would be an explicit analytical relationship, versioned by
classification issue and geography; it must not copy a provider class into
every intersecting Tabia.

## Presentation and model safeguards

The eventual UI must show provider, product, issue date, validity period,
scenario, native geography, and a link to the provider publication. It must
clearly state that FEWS NET classifications are IPC-compatible provider
analysis, not a TSIRD classification or a technical-consensus IPC result.

FEWS NET is used to compare broad historical patterns with TSIRD's
historical response-priority replay. It will remain a separate layer and will
not change a Tabia's draft priority class unless experts define, document, and
approve a future model revision.
