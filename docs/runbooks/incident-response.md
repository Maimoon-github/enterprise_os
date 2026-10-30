# Runbook: Incident Response & Operational Triage

## Common Failure Scenarios

### 1. Social Platform Rate Limiting
- **Symptom:** `SocialGatewayMCP` returns HTTP 429 errors; `notifications/tools/list_changed` emitted.
- **Action:** Check Celery `publishing_queue` retry backoff. Verify tokens in `settings.py` and inspect rate-limit headers in PostgreSQL `analytics_events`.

### 2. LangGraph Execution Stalls on Interrupt
- **Symptom:** Run status stays `running` but no new node transitions occur.
- **Action:** Check `approvals` table for pending review requests. Use Next.js Approvals UI or API `POST /api/v1/approvals/{id}/resume` to resume.

### 3. MinIO Storage Exhaustion
- **Symptom:** Media generation jobs fail with S3 bucket capacity errors.
- **Action:** Check MinIO console at `http://localhost:9001`. Run asset pruning policy on `marketing-raw-assets`.
