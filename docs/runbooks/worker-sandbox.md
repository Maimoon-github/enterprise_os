# Runbook: Rootless Podman Worker Sandboxes

## Overview
Worker sandboxes isolate dynamic Python scripts and browser automation tasks triggered by Agent Skills.

## Building the Sandbox Image
```bash
podman build -t marketing-os-worker-sandbox:latest -f infra/podman/worker.Containerfile .
```

## Security Verification
Verify capability dropping and non-root execution:
```bash
podman run --rm --security-opt=no-new-privileges --cap-drop=ALL marketing-os-worker-sandbox:latest whoami
# Output should return non-root user (e.g. sandboxuser)
```

## Debugging Failed Sandbox Jobs
Inspect worker logs in Celery or check Podman status:
```bash
podman ps -a --filter ancestor=marketing-os-worker-sandbox:latest
```
