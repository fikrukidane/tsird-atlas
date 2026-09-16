# TSIRD development n8n workflow definitions

This directory is the version-controlled source for development workflow JSON.
The running n8n SQLite database is not the source of truth.

- Definitions are imported manually into local n8n and remain inactive by
  default.
- A schedule is enabled only after the activation gate in
  `docs/drought/n8n-workflow-registry.md` is met.
- Workflows call only the internal `tsird-drought-runner` service and must not
  contain credentials, tokens, external webhook URLs, or source payloads.
- Use `GET /runs/{job_id}` to read a runner job status. The legacy
  `/runs/development-test/{job_id}` route is retained only for older imports.

The separate `tsird-drought-production-publisher-v1.development.json` is an
inactive, manual-only release-transfer template. It deliberately does not call
the runner. It contains no production host or credential. Its companion fixed
OpenSSH script uses a verified host key rather than the installed n8n SFTP/SSH
nodes, which cannot pin the server host key; see [the publisher setup
guide](../../docs/drought/n8n-production-publisher-setup.md).

The LST v2 definition remains a development reference only. It is not
scheduleable because the upstream product has been superseded by CLMS LST v3.
