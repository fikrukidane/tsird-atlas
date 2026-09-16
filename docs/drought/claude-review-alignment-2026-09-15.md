# External review alignment — 2026-09-15

## Scope

A read-only, AI-assisted interface review (Claude, via the Cowork browser pane)
inspected Priority Review, Model Studio, Scenario Laboratory, and Pipeline
Control. This note records the TSIRD response to the review; it is not a
scientific validation, independent human review, or external endorsement.

## Implemented in response

- Priority Review consistently describes the local layer as a **Retrospective review
  replay** and it displays a prominent NOT READY warning when the evidence gate is not ready.
  It states that replay flags can exceed the current ceiling and cannot support
  operational priority, allocation, or publication. It describes a retained
  snapshot and evidence rather than implying that the active model is applied live.
- The workspace heading is **Retrospective Evidence Replay**. The displayed
  local draft categories use neutral C1–C4 codes; the underlying class words
  are not shown in the map, legend, selected-Tabia explanation, or comparison table.
- TSIRD replay presentation now uses blue–purple **Replay flags A–D**. FEWS NET
  retains its native warm Food Security Classification palette and dashed
  provider boundaries. The two are intentionally non-equivalent.
- Selected Tabia explanations show the stored draft class separately from the
  neutral replay flag, label CHIRPS 1991–2020 rainfall context, and retain the
  FEWS NET comparison as provider-native context only.
- Priority Review displays enabled and disabled active-model factors and notes
  that a retained snapshot should be interpreted from its stored trace, not by
  retroactively applying a live draft. Snapshot-level model version and factor
  provenance are not yet displayed.
- In Compare mode, FEWS NET is displayed as dashed provider boundaries without
  a fill. Its palette therefore cannot blend with the blue–purple TSIRD replay
  flags. The full FEWS NET palette remains available in its separate context view.
- Stored action text is no longer presented as a recommendation. A selected
  Tabia instead states that local verification is required before considering
  any response.
- Scenario Laboratory moved out of Model Studio’s save form to
  `/map/drought/priority/scenario/`. It uses neutral case numbers, labels both
  reference periods, shows signed land-surface deviations and three-decimal
  NDVI. Interpretation is withheld unless the reviewer records a name, a
  case-specific note, and **Reviewed: no known confounder**. Any other
  confounder category withholds the finding; changing cases clears the record.
  Before any review outcome is selected, the Laboratory explicitly says no
  confounder review is recorded for the case.

## Known remaining issues

- The local web service now requires map assets to revalidate on every load.
  Production reverse proxies must preserve that policy before workshop use.
- Snapshot-level model version and complete factor provenance are still absent
  from each selected replay trace.

## Still requires expert decisions

The platform does not decide whether to exclude or separately treat
2020–2022, which seasonal lags or thresholds fit each agro-ecological setting,
which local confounders apply, or whether population-only exposure belongs in
an agricultural review lens. These are questions for the proposed Tigrayan
candidate review and must be recorded with rationale.

## Requested next external review

Review whether the revised labels, colour separation, NOT READY warning,
model-factor trace, and standalone Laboratory prevent a reasonable user from
mistaking retained evidence or a discussion signal for an operational priority
or FEWS NET/IPC-equivalent classification. Identify remaining interface risks
and suggest only changes that preserve the stated development safeguards.
