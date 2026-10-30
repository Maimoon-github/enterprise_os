# Security, Secrets, and Zero-Trust Proxy Architecture

## Credential Segregation
1. **Zero-Trust Model:** Agent workers, LLMs, and prompt templates never receive raw credentials, database connection strings, S3 master keys, or social platform OAuth client secrets.
2. **Encrypted Storage:** All platform credentials and OAuth refresh tokens are encrypted at rest using AES-256-GCM (`ENCRYPTION_MASTER_KEY`).
3. **Execution Proxying:** When an agent invokes `publish_to_platform(platform, payload, idempotency_key)`, the `SocialGateway` MCP server decrypts the relevant tenant credentials in-memory, executes the platform API call, redacts sensitive headers, and returns only the public post ID and status.

## Rootless Podman Worker Sandboxes
- Dynamic script execution (`scripts/check_tone.py`, `scripts/parse_serp.py`) runs in rootless Podman containers.
- Execution parameters:
  - `--security-opt=no-new-privileges`
  - `--cap-drop=ALL`
  - `--network=none` (except explicitly flagged Playwright browser tasks)
  - Ephemeral read-only root filesystems with 512MB RAM and 1.0 CPU caps.
