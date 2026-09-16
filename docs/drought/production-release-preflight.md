# Drought production release preflight

Run the narrow preflight immediately before an approved data release is
uploaded or activated. It is intentionally **not** a VPS inventory: the
existing inventory remains the baseline. The script neither changes services
nor processes data.

From the known application root, an authorized production operator runs:

```bash
cd /opt/tigrayinsights/apps/tsird
chmod 0755 scripts/preflight-drought-production-release.sh
TSIRD_DROUGHT_MIN_FREE_GIB=2 scripts/preflight-drought-production-release.sh
```

It checks only:

- the existing application, ingress, and serving-release directories;
- whether the production Compose configuration resolves;
- available space on the serving release filesystem (default minimum: 2 GiB,
  adjustable by the release approver against the capacity baseline);
- current Compose service status; and
- that `tsird-api` is running with the release root mounted read-only at
  `/data/drought/production-releases`.

By default it reads the existing untracked `.env.tsird` and the separate
untracked `.env.production.images` file. The latter contains only the three
immutable serving-image references, while the former remains the private base
configuration. An operator may override either path using `TSIRD_BASE_ENV_FILE`
or `TSIRD_IMAGE_ENV_FILE`; do not copy either completed file into Git.

It does not inspect unrelated host files, create accounts, install packages,
pull/build/restart containers, upload a release, change `current.json`, or
contact an external source. A failure is a release stop: investigate without
deleting the active or rollback release.

Use it after deploying the reviewed code/configuration but before the first
release promotion. Record its terminal output with the code commit, image tag,
approved release ID, and visual smoke-test result in the release ledger.
