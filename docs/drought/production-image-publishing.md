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
   tag is the VPS deployment reference.
5. On the VPS, place those three SHA image references in the untracked
   production image environment file based on
   [`.env.production.images.example`](../../.env.production.images.example).
6. Run `scripts/validate-production-image-config.sh`, then pull and activate
   the pinned images through the approved production procedure.

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

## Rollback and failure

- A failed image build does not change the VPS.
- Never deploy a mutable `latest` tag.
- Retain the immediately previous three SHA image references in the release
  ledger and production environment history.
- Rolling back code means pointing the VPS back to the previous verified SHA
  trio; it does not change the approved drought data-release pointer.
