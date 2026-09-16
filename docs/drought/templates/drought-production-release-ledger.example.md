# TSIRD Drought Intelligence — production release ledger

Copy this template into the private release record for each attempted
production release. Do not commit it with credentials, private host details,
reviewer identities, or raw source data.

## Identity and scope

| Field | Record |
| --- | --- |
| Release title / ticket | |
| Release coordinator | |
| Decision authority | |
| Intended environment | Staging / production |
| Public surface | `https://lab.tigrayinsights.net/map/drought/release/` |
| Scope statement | Experimental evidence release; not a forecast, official classification, allocation, or operational directive. |

## Immutable references

| Component | Immutable reference | Previous verified reference |
| --- | --- | --- |
| Source commit | | |
| Source release tag | | |
| Web image SHA tag/digest | | |
| API image SHA tag/digest | | |
| Edge image SHA tag/digest | | |
| Approved drought data-release ID | | |
| Prior data-release ID | | |

Never record a mutable image tag such as `latest`. Record a full image digest
where the registry provides one.

## Evidence release approval

| Check | Result / reference | Reviewer / time |
| --- | --- | --- |
| Local manifest validation | | |
| Named approval recorded in manifest | | |
| Public-boundary/sanitization validation | | |
| Source/provenance and caveat review | | |
| Release data size within capacity budget | | |

## Release-time safety checks

| Check | Result / reference | Operator / time |
| --- | --- | --- |
| Production image configuration guard | | |
| Narrow production preflight | | |
| Image pull completed; no build run on VPS | | |
| API release mount is read-only | | |
| Prior code and data rollback references retained | | |

## Activation and acceptance

| Check | Result / reference | Operator / time |
| --- | --- | --- |
| Activation time (UTC) | | |
| `current.json` points to approved data release | | |
| Public release acceptance script | | |
| Normal browser-load smoke test | | |
| Cache/freshness check | | |
| Public disclaimers and source boundaries visible | | |

## Outcome and rollback

| Field | Record |
| --- | --- |
| Outcome | Activated / stopped / rolled back |
| Publicly observed issue(s) | |
| Rollback decision and reason | |
| Exact rollback image references | |
| Exact rollback data-release pointer | |
| Follow-up owner and due date | |

## Sign-off

| Role | Name | Time (UTC) | Confirmation |
| --- | --- | --- | --- |
| Release approver | | | |
| Production operator | | | |
| Evidence/data reviewer | | | |
