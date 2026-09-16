# Public drought release acceptance check

After the VPS activation step, run this read-only check from a trusted
operator workstation or the VPS itself:

```bash
scripts/verify-drought-public-release.sh https://lab.tigrayinsights.net
```

It verifies the public release viewer, selected approved-release metadata,
each manifest-listed asset, and the two map assets required for the viewer. It
also rejects a replay that exposes development-only action/priority/rule fields
or operational wording.

Before the first approved release exists, verify the intentional waiting state
instead:

```bash
scripts/verify-drought-public-release.sh --expect-unavailable http://127.0.0.1:18080
```

The script performs only HTTP reads and temporary local-file handling. It does
not approve, upload, activate, restart, modify, or delete anything. Record the
result in the release ledger alongside the release ID and visual smoke test.
