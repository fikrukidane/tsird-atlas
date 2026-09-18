# Scripts

Scripts for ETL orchestration and maintenance.

- `provision-drought-release-accounts.sh` is a root-only, production-host
  helper for the constrained SFTP upload and forced-command activation
  accounts used by the future Drought Production Publisher. Read
  `infra/host-nginx/tsird-drought-release-activation.md` before using it. It
  does not transfer or activate a release, reload SSH, or manage containers.
