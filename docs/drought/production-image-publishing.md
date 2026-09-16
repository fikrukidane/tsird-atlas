# TSIRD Drought Intelligence — production image publishing

**Status:** release procedure, 2026-09-16

## Purpose

The constrained production VPS must pull prebuilt serving images. It must not
build source code, retrieve drought inputs, run n8n, or process rasters. The
tagged-source workflow in
[`publish-production-images.yml`](../../.github/workflows/publish-production-images.yml)
builds and publishes the three serving images to GitHub Container Registry
(GHCR):

| Component | GHCR image |
| --- | --- |
| Static web | `ghcr.io/fikrukidane/tsird-atlas-web` |
| API | `ghcr.io/fikrukidane/tsird-atlas-api` |
| Edge proxy | `ghcr.io/fikrukidane/tsird-atlas-edge` |

The workflow runs only for a deliberately created `tsird-drought-v*` tag or a
manual dispatch. It does not publish images for every development commit.

## Release sequence

1. Complete local review and relevant checks on the release branch.
2. Create and push an annotated, immutable `tsird-drought-vYYYY.MM.DD.N` tag
   at the reviewed commit.
3. Wait for the **Publish production images** GitHub Actions workflow to
   succeed for `web`, `api`, and `edge`.
4. Record each resulting immutable `sha-<commit>` image tag in the release
   ledger. The human-readable release tag is useful for navigation; the SHA
   tag is the VPS deployment reference. Use the private
   [release ledger template](templates/drought-production-release-ledger.example.md)
   to keep the source tag, image digest, approved data-release ID and rollback
   trio together.
5. On the VPS, place those three SHA image references in the untracked
   `.env.production.images` file based on
   [`.env.production.images.example`](../../.env.production.images.example).
6. The production guards read both `.env.tsird` and
   `.env.production.images` by default. Run
   `scripts/validate-production-image-config.sh`, then use the same two
   `--env-file` arguments when pulling and activating the pinned images through
   the approved production procedure.

The production Compose overlay rejects placeholder image references, removes
`build:` for the three serving components, and excludes development ETL from
the default production profile. See the
[production release plan](production-release-plan.md) for the surrounding
data-release and rollback controls.

## Required GitHub repository setting

GHCR must allow this repository's workflow token to write packages. The
workflow uses the repository-scoped `GITHUB_TOKEN` and requests only
`contents: read` and `packages: write`; no registry password belongs in the
repository or VPS configuration.

If GHCR visibility is private, the VPS needs a separately scoped,
read-only package-pull credential held only in its untracked environment
configuration. Prefer public read access for public, non-secret serving images
only if that matches the project owner's release policy.

## Candidate `tsird-drought-v0.1.0-rc.1`

The first CI-only candidate was built from commit
`1f88ef7f9ec7af4cdbcd5fffd56fd81e5a03df83`. Its pull references are:

```text
TSIRD_WEB_IMAGE=ghcr.io/fikrukidane/tsird-atlas-web:sha-1f88ef7
TSIRD_API_IMAGE=ghcr.io/fikrukidane/tsird-atlas-api:sha-1f88ef7
TSIRD_EDGE_IMAGE=ghcr.io/fikrukidane/tsird-atlas-edge:sha-1f88ef7
```

These are suitable only for a staging/pull rehearsal until the release ledger
records the image digests and the production approval gate is complete. They
do not activate a drought data release.

## Rollback and failure

- A failed image build does not change the VPS.
- Never deploy a mutable `latest` tag.
- Retain the immediately previous three SHA image references in the release
  ledger and production environment history.
- Rolling back code means pointing the VPS back to the previous verified SHA
  trio; it does not change the approved drought data-release pointer.
