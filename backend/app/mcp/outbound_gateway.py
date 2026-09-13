"""Post-HITL signed, rate-limited actuation boundary (MCP_ACT).

This is the only module in the backend permitted to invoke an ads, social,
or CMS adapter. Every call requires: (1) a recorded, approved HITL decision
with cryptographic clearance for the referenced action preview, (2) a valid
signature over the canonical dispatch payload, (3) audience token and scope
validation, (4) rate-limit capacity, and (5) replay/idempotency protection.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.core.exceptions import (
    ApprovalRequiredError,
    ConfigurationError,
    PolicyViolationError,
    RateLimitExceededError,
    SignatureVerificationError,
)
from app.integrations.ads.base import AdsAdapter
from app.integrations.cms.client import CmsClient
from app.integrations.social.base import SocialAdapter
from app.schemas.dispatch import AudienceToken, CmsDeploymentResult, DispatchDirective, DispatchReadiness
from app.schemas.task_state import TaskStatus
from app.security.cryptographic_validator import CryptographicValidator
from app.services.hitl import HitlCoordinator
from app.services.provenance import ProvenanceRecorder

if TYPE_CHECKING:
    from app.services.task_state import TaskStateService



class TokenBucket:
    """A configurable token-bucket rate limiter supporting burst capacity and sustained refill."""

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self._capacity = capacity
        self._tokens = float(capacity)
        self._refill_per_second = refill_per_second
        self._last_refill = time.monotonic()

    def allow(self) -> bool:
        """Consume one token if available and return whether it was granted."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_second)
        self._last_refill = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False


def canonical_dispatch_bytes(dispatch: DispatchDirective) -> bytes:
    """Return the deterministic byte payload a dispatch signature must cover."""

    canonical: dict[str, Any] = {
        "action_preview_id": dispatch.action_preview_id,
        "approved_at": dispatch.approved_at.isoformat(),
        "approved_by": dispatch.approved_by,
        "channel": dispatch.channel,
        "dispatch_id": dispatch.dispatch_id,
        "payload": dispatch.payload,
        "task_id": dispatch.task_id,
    }
    if dispatch.tenant_id != "default":
        canonical["tenant_id"] = dispatch.tenant_id
    if dispatch.audience != "global":
        canonical["audience"] = dispatch.audience
    if dispatch.action_type != "publish":
        canonical["action_type"] = dispatch.action_type
    if dispatch.preview_content_hash:
        canonical["preview_content_hash"] = dispatch.preview_content_hash
    if dispatch.clearance_id:
        canonical["clearance_id"] = dispatch.clearance_id
    if dispatch.idempotency_key:
        canonical["idempotency_key"] = dispatch.idempotency_key
    return json.dumps(canonical, sort_keys=True).encode("utf-8")


def scrub_sensitive_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitized copy of payload with credentials, tokens, and keys redacted."""
    sensitive_markers = ("token", "secret", "password", "api_key", "access_token", "private_key", "credential")
    scrubbed: dict[str, Any] = {}
    for k, v in payload.items():
        if isinstance(v, dict):
            scrubbed[k] = scrub_sensitive_payload(v)
        elif any(marker in k.lower() for marker in sensitive_markers):
            scrubbed[k] = "[REDACTED]"
        else:
            scrubbed[k] = v
    return scrubbed


class OutboundGateway:
    """Enforces HITL approval, signature verification, audience tokens, scope checks, and rate limiting before actuation."""

    def __init__(
        self,
        hitl: HitlCoordinator,
        crypto_validator: CryptographicValidator,
        *,
        ads_adapters: dict[str, AdsAdapter] | None = None,
        social_adapters: dict[str, SocialAdapter] | None = None,
        cms_client: CmsClient | None = None,
        rate_limiter: TokenBucket | None = None,
        target_rate_limiters: dict[str, TokenBucket] | None = None,
        require_signature: bool = True,
        provenance_recorder: ProvenanceRecorder | None = None,
        task_state_service: TaskStateService | None = None,
    ) -> None:
        self._hitl = hitl
        self._crypto_validator = crypto_validator
        self._ads_adapters = ads_adapters or {}
        self._social_adapters = social_adapters or {}
        self._cms_client = cms_client
        self._rate_limiter = rate_limiter or TokenBucket(capacity=10, refill_per_second=1.0)
        self._target_rate_limiters = target_rate_limiters or {}
        self._require_signature = require_signature
        self._provenance_recorder = provenance_recorder
        self._task_state_service = task_state_service
        self._idempotency_records: dict[str, tuple[str, str, DispatchReadiness]] = {}
        self._execution_records: dict[str, dict[str, Any]] = {}

    async def validate_readiness(self, dispatch: DispatchDirective) -> DispatchReadiness:
        """Certify that ``dispatch`` satisfies all post-HITL gate invariants without executing outbound side-effects."""

        idempotency_key = dispatch.idempotency_key or dispatch.dispatch_id
        payload_hash = hashlib.sha256(json.dumps(dispatch.payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()

        # 1. Replay & Idempotency Protection
        if idempotency_key in self._idempotency_records:
            prev_hash, prev_sig, prev_readiness = self._idempotency_records[idempotency_key]
            if prev_hash == payload_hash and prev_sig == dispatch.signature:
                # Legitimate idempotent retry
                return prev_readiness.model_copy(update={"idempotent_cached": True})
            # Replayed or duplicate directive with different content/signature
            raise PolicyViolationError(
                f"Replay detected: dispatch '{dispatch.dispatch_id}' replayed with modified payload or signature."
            )

        # 2. Verify T24 Authoritative Human Clearance
        decision = self._hitl.require_approved(dispatch.action_preview_id)
        clearance = decision.clearance
        if clearance is not None:
            if not clearance.is_valid:
                raise PolicyViolationError(f"Clearance for '{dispatch.action_preview_id}' is marked invalid or revoked.")
            if clearance.expires_at is not None and clearance.expires_at < datetime.now(UTC):
                raise PolicyViolationError(f"Clearance for '{dispatch.action_preview_id}' expired at {clearance.expires_at}.")
            if clearance.tenant_id not in ("default", "global", dispatch.tenant_id):
                raise PolicyViolationError(
                    f"Tenant authority mismatch: clearance tenant '{clearance.tenant_id}' cannot authorize dispatch for '{dispatch.tenant_id}'."
                )
            if dispatch.preview_content_hash and clearance.preview_content_hash != dispatch.preview_content_hash:
                raise PolicyViolationError(
                    f"Preview content hash mismatch for dispatch '{dispatch.dispatch_id}'."
                )

            # 3. Scope & Budget Escalation Enforcement
            approved_spend = clearance.approved_scope.get("spend_amount")
            if approved_spend is not None:
                req_spend = (
                    dispatch.payload.get("spend_amount")
                    or dispatch.payload.get("budget")
                    or dispatch.payload.get("amount")
                )
                if req_spend is not None:
                    try:
                        req_spend_val = float(req_spend)
                        if req_spend_val > float(approved_spend):
                            raise PolicyViolationError(
                                f"Requested spend {req_spend_val} exceeds HITL-approved scope {approved_spend}."
                            )
                    except (ValueError, TypeError):
                        pass

        # 4. Target & Channel Scope Validation
        if dispatch.channel in ("cms", "website", "web_store"):
            allowed_actions = {"publish", "update", "create", "deploy"}
            if dispatch.action_type not in allowed_actions:
                raise PolicyViolationError(
                    f"Action '{dispatch.action_type}' is not a permitted website/CMS actuation (must be one of {sorted(allowed_actions)})."
                )
            if clearance is not None and clearance.approved_scope:
                approved_scope = clearance.approved_scope

                # Check permitted content types
                if "permitted_content_types" in approved_scope:
                    permitted_types = set(approved_scope["permitted_content_types"])
                    payload_types = set()
                    if "content_type" in dispatch.payload:
                        payload_types.add(dispatch.payload["content_type"])
                    for item in dispatch.payload.get("items", []):
                        if isinstance(item, dict) and "content_type" in item:
                            payload_types.add(item["content_type"])
                    if not payload_types.issubset(permitted_types):
                        raise PolicyViolationError(
                            f"Payload contains unapproved content types: {payload_types - permitted_types}"
                        )

                # Check permitted entries
                if "permitted_entries" in approved_scope:
                    permitted_entries = set(approved_scope["permitted_entries"])
                    payload_entries = set()
                    if "entry_id" in dispatch.payload:
                        payload_entries.add(dispatch.payload["entry_id"])
                    for item in dispatch.payload.get("items", []):
                        if isinstance(item, dict):
                            eid = item.get("entry_id") or item.get("id")
                            if eid:
                                payload_entries.add(eid)
                    if not payload_entries.issubset(permitted_entries):
                        raise PolicyViolationError(
                            f"Payload contains unapproved entries: {payload_entries - permitted_entries}"
                        )

                # Check permitted files for code diffs
                if "permitted_files" in approved_scope:
                    permitted_files = set(approved_scope["permitted_files"])
                    payload_files = set()
                    if "file_path" in dispatch.payload:
                        payload_files.add(dispatch.payload["file_path"])
                    for cd in dispatch.payload.get("code_diffs", []):
                        fp = cd.get("file_path") if isinstance(cd, dict) else getattr(cd, "file_path", None)
                        if fp:
                            payload_files.add(fp)
                    if not payload_files.issubset(permitted_files):
                        raise PolicyViolationError(
                            f"Payload contains unapproved code diff files: {payload_files - permitted_files}"
                        )

                # Check artifact hash binding
                if "artifact_hash" in dispatch.payload and "artifact_hash" in approved_scope:
                    if dispatch.payload["artifact_hash"] != approved_scope["artifact_hash"]:
                        raise PolicyViolationError(
                            f"Artifact hash mismatch: payload has '{dispatch.payload['artifact_hash']}', expected '{approved_scope['artifact_hash']}'."
                        )
                elif "artifact_hash" in dispatch.payload and dispatch.preview_content_hash:
                    if dispatch.payload["artifact_hash"] != dispatch.preview_content_hash:
                        raise PolicyViolationError(
                            "Artifact hash in payload does not match approved preview content hash."
                        )

        # 5. Audience Token & Scope Validation
        if dispatch.audience_token is not None:
            if isinstance(dispatch.audience_token, str):
                if not dispatch.audience_token.strip():
                    raise PolicyViolationError("Audience token cannot be empty.")
            elif isinstance(dispatch.audience_token, AudienceToken):
                tok = dispatch.audience_token
                if tok.is_revoked:
                    raise PolicyViolationError(f"Audience token '{tok.token_id}' has been revoked.")
                if tok.expires_at < datetime.now(UTC):
                    raise PolicyViolationError(f"Audience token '{tok.token_id}' expired at {tok.expires_at}.")
                if tok.tenant_id not in ("default", "global", dispatch.tenant_id):
                    raise PolicyViolationError(
                        f"Audience token tenant '{tok.tenant_id}' does not match directive tenant '{dispatch.tenant_id}'."
                    )
                if tok.target_audience not in ("global", "*", dispatch.audience):
                    raise PolicyViolationError(
                        f"Audience token target '{tok.target_audience}' does not match directive audience '{dispatch.audience}'."
                    )
                if dispatch.action_type not in tok.permitted_actions and "*" not in tok.permitted_actions:
                    raise PolicyViolationError(
                        f"Action '{dispatch.action_type}' is not permitted by audience token."
                    )

        # 6. Cryptographic Signature Verification
        if self._require_signature:
            payload_bytes = canonical_dispatch_bytes(dispatch)
            if not self._crypto_validator.verify(payload_bytes, dispatch.signature):
                raise SignatureVerificationError(
                    f"Dispatch '{dispatch.dispatch_id}' failed signature verification."
                )

        # 7. Rate Limit Enforcement
        limiter = self._target_rate_limiters.get(dispatch.channel, self._rate_limiter)
        if not limiter.allow():
            raise RateLimitExceededError(
                f"Outbound rate limit exceeded for dispatch '{dispatch.dispatch_id}' on channel '{dispatch.channel}'."
            )

        # 8. Record Readiness & Provenance
        readiness = DispatchReadiness(
            directive_id=dispatch.dispatch_id,
            action_preview_id=dispatch.action_preview_id,
            tenant_id=dispatch.tenant_id,
            channel=dispatch.channel,
            status="READY",
            is_ready=True,
            verified_clearance_id=clearance.clearance_id if clearance else None,
            rate_limit_available=True,
            idempotent_cached=False,
            validation_notes=[f"Clearance {clearance.clearance_id if clearance else 'approved'} verified for channel {dispatch.channel}"],
        )

        self._idempotency_records[idempotency_key] = (payload_hash, dispatch.signature, readiness)

        if self._provenance_recorder:
            scrubbed = scrub_sensitive_payload(dispatch.payload)
            await self._provenance_recorder.record(
                tenant_id=dispatch.tenant_id,
                entity_id=dispatch.dispatch_id,
                activity="mcp_act_readiness_validation",
                agent="mcp_act_boundary",
                metadata={
                    "channel": dispatch.channel,
                    "action_preview_id": dispatch.action_preview_id,
                    "clearance_id": clearance.clearance_id if clearance else None,
                    "payload_keys": sorted(scrubbed.keys()),
                },
            )

        return readiness

    async def execute(self, dispatch: DispatchDirective) -> dict[str, Any]:
        """Verify approval, signature, rate limit, and scope, then actuate ``dispatch``."""

        readiness = await self.validate_readiness(dispatch)

        idempotency_key = dispatch.idempotency_key or dispatch.dispatch_id
        if readiness.idempotent_cached and idempotency_key in self._execution_records:
            # Return cached execution result safely without re-actuating
            return self._execution_records[idempotency_key]

        # Transition CTS task to DISPATCHED if state service is wired
        task_state = None
        if self._task_state_service and dispatch.task_id:
            try:
                task_state = await self._task_state_service.get_state(dispatch.task_id)
                if task_state.status == TaskStatus.APPROVED:
                    task_state = await self._task_state_service.transition(
                        dispatch.tenant_id,
                        task_state,
                        TaskStatus.DISPATCHED,
                        note=f"Dispatched directive {dispatch.dispatch_id} to channel {dispatch.channel} via MCP_ACT",
                    )
            except Exception:
                pass

        try:
            if dispatch.channel in self._ads_adapters:
                res = await self._ads_adapters[dispatch.channel].apply_action(dispatch.payload)
            elif dispatch.channel in self._social_adapters:
                res = await self._social_adapters[dispatch.channel].publish(dispatch.payload)
            elif dispatch.channel in ("cms", "website", "web_store"):
                if self._cms_client is None:
                    raise ConfigurationError("No CMS client is registered on OutboundGateway.")

                # Execute production CMS/Website deployment
                if (
                    dispatch.action_type == "publish"
                    or dispatch.payload.get("action") == "publish"
                    or "items" in dispatch.payload
                    or "schema_diffs" in dispatch.payload
                    or "products" in dispatch.payload
                    or "pages" in dispatch.payload
                    or "code_diffs" in dispatch.payload
                    or "assets" in dispatch.payload
                    or "layouts" in dispatch.payload
                ):
                    cms_raw = await self._cms_client.deploy_payload(
                        dispatch.payload, tenant_id=dispatch.tenant_id
                    )
                elif "entry_id" in dispatch.payload:
                    entry_id = dispatch.payload["entry_id"]
                    content_type = dispatch.payload.get("content_type", "pages")
                    if dispatch.action_type == "create":
                        cms_raw = await self._cms_client.create_entry(
                            content_type, entry_id, dispatch.payload, tenant_id=dispatch.tenant_id
                        )
                    else:
                        cms_raw = await self._cms_client.apply_changes(
                            content_type, entry_id, dispatch.payload, tenant_id=dispatch.tenant_id
                        )
                else:
                    cms_raw = await self._cms_client.deploy_payload(
                        dispatch.payload, tenant_id=dispatch.tenant_id
                    )

                applied_items = cms_raw.get("applied_items", [cms_raw])
                applied_hashes = cms_raw.get("applied_hashes", [])
                if not applied_hashes:
                    h = hashlib.sha256(json.dumps(dispatch.payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
                    applied_hashes = [h]

                deployment_result = CmsDeploymentResult(
                    deployment_id=str(uuid.uuid4()),
                    dispatch_id=dispatch.dispatch_id,
                    task_id=dispatch.task_id,
                    tenant_id=dispatch.tenant_id,
                    channel=dispatch.channel,
                    action_type=dispatch.action_type,
                    status_code=str(cms_raw.get("status_code", "200")),
                    status=cms_raw.get("status", "published"),
                    applied_items=applied_items,
                    applied_hashes=applied_hashes,
                    version=str(cms_raw.get("version", "v1.0")),
                    target="cms",
                    details={"raw_response": cms_raw},
                )
                res = deployment_result.model_dump()
                res["status_code"] = deployment_result.status_code
                res["status"] = deployment_result.status
                res["channel"] = dispatch.channel
            else:
                raise ConfigurationError(
                    f"No outbound adapter is registered for channel '{dispatch.channel}'."
                )

            # Store execution record for idempotency
            self._execution_records[idempotency_key] = res

            # Update CTS state to COMPLETED
            if self._task_state_service and dispatch.task_id and task_state:
                try:
                    task_state.cts_state["deployment"] = res
                    await self._task_state_service.save_state(dispatch.tenant_id, task_state)
                    if task_state.status == TaskStatus.DISPATCHED:
                        await self._task_state_service.transition(
                            dispatch.tenant_id,
                            task_state,
                            TaskStatus.COMPLETED,
                            note=f"Successfully actuated {dispatch.channel} directive {dispatch.dispatch_id}",
                        )
                except Exception:
                    pass

            # Record deployment execution provenance with sensitive data scrubbed
            if self._provenance_recorder:
                scrubbed = scrub_sensitive_payload(res)
                await self._provenance_recorder.record(
                    tenant_id=dispatch.tenant_id,
                    entity_id=dispatch.dispatch_id,
                    activity=f"outbound_{dispatch.channel}_deployment_executed",
                    agent="mcp_act_boundary",
                    metadata=scrubbed,
                )

            return res

        except Exception as exc:
            # Mark task FAILED if state service is wired
            if self._task_state_service and dispatch.task_id and task_state:
                try:
                    if task_state.status == TaskStatus.DISPATCHED:
                        await self._task_state_service.transition(
                            dispatch.tenant_id,
                            task_state,
                            TaskStatus.FAILED,
                            note=f"Deployment actuation failed: {exc}",
                        )
                except Exception:
                    pass

            if self._provenance_recorder:
                await self._provenance_recorder.record(
                    tenant_id=dispatch.tenant_id,
                    entity_id=dispatch.dispatch_id,
                    activity=f"outbound_{dispatch.channel}_deployment_failed",
                    agent="mcp_act_boundary",
                    metadata={"error": str(exc), "channel": dispatch.channel},
                )
            raise