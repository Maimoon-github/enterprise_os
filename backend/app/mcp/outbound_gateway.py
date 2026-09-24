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
from app.schemas.dispatch import (
    AudienceToken,
    CmsDeploymentResult,
    DispatchDirective,
    DispatchReadiness,
    PaidCampaignDeploymentResult,
    SocialPostDeploymentResult,
)
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
    if getattr(dispatch, "policy_version", None):
        canonical["policy_version"] = dispatch.policy_version
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
        if clearance is None:
            raise PolicyViolationError(
                f"Approved decision for '{dispatch.action_preview_id}' lacks signed clearance record."
            )
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
            if dispatch.policy_version and getattr(clearance, "policy_version", None):
                if dispatch.policy_version != clearance.policy_version:
                    raise PolicyViolationError(
                        f"Policy version mismatch: dispatch '{dispatch.policy_version}' != clearance '{clearance.policy_version}'."
                    )

            # 3. Scope & Budget Escalation Enforcement
            approved_spend = (
                clearance.approved_scope.get("spend_amount")
                or clearance.approved_scope.get("budget")
                or clearance.approved_scope.get("max_budget")
                or clearance.approved_scope.get("daily_budget")
            )
            if approved_spend is not None:
                req_spend = (
                    dispatch.payload.get("spend_amount")
                    or dispatch.payload.get("budget")
                    or dispatch.payload.get("daily_budget")
                    or dispatch.payload.get("lifetime_budget")
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

            # Bid Target Escalation Enforcement
            approved_bid = (
                clearance.approved_scope.get("max_bid")
                or clearance.approved_scope.get("bid_target")
                or clearance.approved_scope.get("target_cpa")
                or clearance.approved_scope.get("bid_amount")
            )
            if approved_bid is not None:
                req_bid = (
                    dispatch.payload.get("bid_amount")
                    or dispatch.payload.get("bid_target")
                    or dispatch.payload.get("target_cpa")
                    or dispatch.payload.get("max_bid")
                    or dispatch.payload.get("bid")
                )
                if req_bid is not None:
                    try:
                        req_bid_val = float(req_bid)
                        if req_bid_val > float(approved_bid):
                            raise PolicyViolationError(
                                f"Requested bid {req_bid_val} exceeds HITL-approved bid target {approved_bid}."
                            )
                    except (ValueError, TypeError):
                        pass

            # Creative & Claim Reference Binding
            approved_creatives = set(
                clearance.approved_scope.get("creative_refs")
                or clearance.approved_scope.get("approved_creatives")
                or []
            )
            if approved_creatives:
                payload_creatives = set()
                if "creative_id" in dispatch.payload:
                    payload_creatives.add(str(dispatch.payload["creative_id"]))
                if "creative_refs" in dispatch.payload:
                    refs = dispatch.payload["creative_refs"]
                    if isinstance(refs, list):
                        payload_creatives.update(str(r) for r in refs)
                    elif isinstance(refs, (str, int)):
                        payload_creatives.add(str(refs))
                if payload_creatives and not payload_creatives.issubset(approved_creatives):
                    raise PolicyViolationError(
                        f"Payload contains unapproved creative references: {sorted(payload_creatives - approved_creatives)} (approved: {sorted(approved_creatives)})."
                    )

            approved_claims = set(
                clearance.approved_scope.get("claim_ids")
                or clearance.approved_scope.get("approved_claims")
                or []
            )
            if approved_claims:
                payload_claims = set()
                if "claim_id" in dispatch.payload:
                    payload_claims.add(str(dispatch.payload["claim_id"]))
                if "claim_ids" in dispatch.payload:
                    cids = dispatch.payload["claim_ids"]
                    if isinstance(cids, list):
                        payload_claims.update(str(c) for c in cids)
                    elif isinstance(cids, (str, int)):
                        payload_claims.add(str(cids))
                if payload_claims and not payload_claims.issubset(approved_claims):
                    unapproved_claim = sorted(payload_claims - approved_claims)[0]
                    raise PolicyViolationError(
                        f"Payload contains unapproved claim references: Claim '{unapproved_claim}' not in approved clearance (approved: {sorted(approved_claims)})."
                    )

            # Media Asset References & Hash Binding
            approved_media_assets = set(
                clearance.approved_scope.get("media_asset_ids")
                or clearance.approved_scope.get("asset_ids")
                or clearance.approved_scope.get("media_refs")
                or []
            )
            if approved_media_assets:
                payload_media = set()
                if "media_id" in dispatch.payload:
                    payload_media.add(str(dispatch.payload["media_id"]))
                if "video_id" in dispatch.payload:
                    payload_media.add(str(dispatch.payload["video_id"]))
                if "asset_id" in dispatch.payload:
                    payload_media.add(str(dispatch.payload["asset_id"]))
                if "media_asset_ids" in dispatch.payload:
                    m_ids = dispatch.payload["media_asset_ids"]
                    if isinstance(m_ids, list):
                        payload_media.update(str(m) for m in m_ids)
                    elif isinstance(m_ids, (str, int)):
                        payload_media.add(str(m_ids))
                if payload_media and not payload_media.issubset(approved_media_assets):
                    unapproved_asset = sorted(payload_media - approved_media_assets)[0]
                    raise PolicyViolationError(
                        f"Payload contains unapproved media assets: Media asset '{unapproved_asset}' not in approved clearance (approved: {sorted(approved_media_assets)})."
                    )

            # Copy / Text Integrity Enforcement
            expected_copy = (
                clearance.approved_scope.get("approved_copy")
                or clearance.approved_scope.get("text")
                or clearance.approved_scope.get("copy")
            )
            if expected_copy is not None:
                actual_copy = (
                    dispatch.payload.get("text")
                    or dispatch.payload.get("copy")
                    or dispatch.payload.get("caption")
                    or dispatch.payload.get("description")
                    or dispatch.payload.get("body")
                )
                if actual_copy is not None and actual_copy != expected_copy:
                    raise PolicyViolationError(
                        "Payload copy does not match HITL-approved copy."
                    )
            expected_copy_hash = clearance.approved_scope.get("copy_hash") or clearance.approved_scope.get("text_hash")
            if expected_copy_hash is not None:
                actual_copy_str = str(
                    dispatch.payload.get("text")
                    or dispatch.payload.get("copy")
                    or dispatch.payload.get("caption")
                    or dispatch.payload.get("description")
                    or dispatch.payload.get("body")
                    or ""
                )
                actual_copy_hash = hashlib.sha256(actual_copy_str.encode("utf-8")).hexdigest()
                if actual_copy_hash != expected_copy_hash:
                    raise PolicyViolationError(
                        f"Copy hash mismatch: payload copy hash '{actual_copy_hash}' does not match approved '{expected_copy_hash}'."
                    )

            # Schedule Scope Binding
            expected_schedule = clearance.approved_scope.get("scheduled_at") or clearance.approved_scope.get("scheduled_time")
            if expected_schedule is not None:
                actual_schedule = dispatch.payload.get("scheduled_at") or dispatch.payload.get("scheduled_time")
                if actual_schedule is not None and str(actual_schedule) != str(expected_schedule):
                    raise PolicyViolationError(
                        f"Schedule mismatch: payload specifies '{actual_schedule}', but HITL approved '{expected_schedule}'."
                    )

            # Account / Customer / Channel ID Scope Enforcement
            for acc_field in ("account_id", "ad_account_id", "customer_id", "advertiser_id", "ig_user_id", "author_id", "channel_id"):
                if acc_field in clearance.approved_scope:
                    expected_acc = str(clearance.approved_scope[acc_field])
                    if acc_field in dispatch.payload:
                        actual_acc = str(dispatch.payload[acc_field])
                        if actual_acc != expected_acc:
                            raise PolicyViolationError(
                                f"Account mismatch on '{acc_field}' (Social account ID mismatch): payload specifies '{actual_acc}', but HITL approved '{expected_acc}'."
                            )

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
                        if isinstance(item, dict) and "entry_id" in item:
                            payload_entries.add(item["entry_id"])
                    if not payload_entries.issubset(permitted_entries):
                        raise PolicyViolationError(
                            f"Payload contains unapproved entry IDs: {payload_entries - permitted_entries}"
                        )

                # Check max item count
                if "max_items" in approved_scope:
                    max_items = int(approved_scope["max_items"])
                    item_count = len(dispatch.payload.get("items", [])) or (1 if "entry_id" in dispatch.payload else 0)
                    if item_count > max_items:
                        raise PolicyViolationError(
                            f"Payload item count {item_count} exceeds approved limit of {max_items}."
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

                # Check strict artifact hash matching
                if "artifact_hash" in approved_scope:
                    if "artifact_hash" not in dispatch.payload:
                        raise PolicyViolationError(
                            "Payload missing required artifact hash approved in HITL scope."
                        )
                    if dispatch.payload["artifact_hash"] != approved_scope["artifact_hash"]:
                        raise PolicyViolationError(
                            f"Artifact hash mismatch: payload has '{dispatch.payload['artifact_hash']}', expected '{approved_scope['artifact_hash']}'."
                        )
                elif "artifact_hash" in dispatch.payload and dispatch.preview_content_hash:
                    if dispatch.payload["artifact_hash"] != dispatch.preview_content_hash:
                        raise PolicyViolationError(
                            "Artifact hash in payload does not match approved preview content hash."
                        )
        elif (
            dispatch.channel in self._social_adapters
            or dispatch.channel in ("instagram", "x", "youtube", "tiktok_social", "threads", "facebook_social")
            or (dispatch.channel == "tiktok" and "tiktok" not in self._ads_adapters)
        ):
            # Canonical T28 social scope is strictly Instagram, X, YouTube
            canonical_social_channels = {"instagram", "x", "youtube"}
            if dispatch.channel in ("tiktok", "tiktok_social"):
                is_authorized = False
                if clearance is not None and clearance.approved_scope:
                    authorized_channels = [str(c).lower() for c in clearance.approved_scope.get("authorized_channels", [])]
                    authorized_platforms = [str(p).lower() for p in clearance.approved_scope.get("authorized_platforms", [])]
                    permitted_channels = [str(c).lower() for c in clearance.approved_scope.get("permitted_channels", [])]
                    if any(t in authorized_channels or t in authorized_platforms or t in permitted_channels for t in ("tiktok", "tiktok_social")):
                        is_authorized = True
                if dispatch.audience_token is not None and isinstance(dispatch.audience_token, AudienceToken):
                    if any(t in dispatch.audience_token.permitted_actions for t in ("tiktok", "tiktok_social")):
                        is_authorized = True
                if not is_authorized:
                    raise PolicyViolationError(
                        "Channel 'tiktok' is outside canonical T28 scope and not permitted without explicit HITL authorization in approved scope."
                    )
            elif dispatch.channel not in canonical_social_channels and dispatch.channel not in ("twitter",):
                raise PolicyViolationError(
                    f"Unsupported social channel '{dispatch.channel}'. Permitted canonical channels are {sorted(canonical_social_channels)}."
                )

            # Native scheduling capability enforcement:
            # If scheduling is requested on a platform without native automated scheduling (e.g. X standard tweet endpoint), fail explicitly.
            is_scheduling_requested = bool(dispatch.payload.get("scheduled_at") or dispatch.payload.get("scheduled_time"))
            if is_scheduling_requested and dispatch.channel in ("x", "twitter"):
                raise PolicyViolationError(
                    f"Channel '{dispatch.channel}' does not support native scheduled posts or automated scheduling on the standard publishing endpoint; cannot silently publish immediately."
                )
        elif (
            dispatch.channel in ("meta", "google", "tiktok", "linkedin")
            or dispatch.channel in self._ads_adapters
            or dispatch.channel in ("snapchat", "pinterest", "reddit", "bing")
        ):
            # Canonical T27 paid-media scope is strictly Meta, Google, TikTok
            canonical_platforms = {"meta", "google", "tiktok"}
            if dispatch.channel == "linkedin":
                is_authorized = False
                if clearance is not None and clearance.approved_scope:
                    authorized_platforms = [str(p).lower() for p in clearance.approved_scope.get("authorized_platforms", [])]
                    permitted_channels = [str(c).lower() for c in clearance.approved_scope.get("permitted_channels", [])]
                    if "linkedin" in authorized_platforms or "linkedin" in permitted_channels:
                        is_authorized = True
                if dispatch.audience_token is not None and isinstance(dispatch.audience_token, AudienceToken):
                    if "linkedin" in dispatch.audience_token.permitted_actions:
                        is_authorized = True
                if not is_authorized:
                    raise PolicyViolationError(
                        "Platform 'linkedin' is not permitted for canonical T27 actuation without explicit HITL authorization in approved scope."
                    )
            elif dispatch.channel not in canonical_platforms:
                # If channel is an unapproved ad platform, fail closed
                raise PolicyViolationError(
                    f"Unsupported or unapproved paid-media platform '{dispatch.channel}'. Permitted canonical platforms are {sorted(canonical_platforms)}."
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

        # 7. Task State Screening: Fail closed if task is non-executable
        if self._task_state_service is not None and dispatch.task_id:
            try:
                task_state = await self._task_state_service.get_state(dispatch.task_id)
                if task_state is not None:
                    if task_state.status in (TaskStatus.HELD, TaskStatus.REJECTED, TaskStatus.FAILED) or task_state.hold_reason:
                        raise PolicyViolationError(
                            f"Task '{dispatch.task_id}' is in non-executable state '{task_state.status.value}'."
                        )
                    task_tenant = getattr(task_state, "tenant_id", None)
                    if task_tenant is not None and task_tenant not in ("default", "global", dispatch.tenant_id):
                        raise PolicyViolationError(
                            f"Tenant authority mismatch: task tenant '{task_tenant}' cannot authorize dispatch for '{dispatch.tenant_id}'."
                        )
            except PolicyViolationError:
                raise
            except Exception:
                pass

        # 8. Rate Limit Enforcement
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
            task_state = await self._task_state_service.get_state(dispatch.task_id)
            if task_state is not None:
                if task_state.status in (TaskStatus.HELD, TaskStatus.REJECTED, TaskStatus.FAILED) or task_state.hold_reason:
                    raise PolicyViolationError(
                        f"Task '{dispatch.task_id}' is in non-executable state '{task_state.status.value}'."
                    )
                task_tenant = getattr(task_state, "tenant_id", None)
                if task_tenant is not None and task_tenant not in ("default", "global", dispatch.tenant_id):
                    raise PolicyViolationError(
                        f"Tenant authority mismatch: task tenant '{task_tenant}' cannot authorize dispatch for '{dispatch.tenant_id}'."
                    )
                if task_state.status == TaskStatus.APPROVED:
                    task_state = await self._task_state_service.transition(
                        dispatch.tenant_id,
                        task_state,
                        TaskStatus.DISPATCHED,
                        note=f"Dispatched directive {dispatch.dispatch_id} to channel {dispatch.channel} via MCP_ACT",
                    )

        # Persist dispatch intent and idempotency identity BEFORE external execution
        payload_hash = hashlib.sha256(json.dumps(dispatch.payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        self._execution_records[idempotency_key] = {
            "status": "DISPATCH_INTENT",
            "dispatch_id": dispatch.dispatch_id,
            "idempotency_key": idempotency_key,
            "channel": dispatch.channel,
            "payload_hash": payload_hash,
            "tenant_id": dispatch.tenant_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if self._provenance_recorder:
            await self._provenance_recorder.record(
                tenant_id=dispatch.tenant_id,
                entity_id=dispatch.dispatch_id,
                activity="outbound_dispatch_intent_persisted",
                agent="mcp_act_boundary",
                metadata={
                    "channel": dispatch.channel,
                    "idempotency_key": idempotency_key,
                    "action_preview_id": dispatch.action_preview_id,
                    "task_id": dispatch.task_id,
                },
            )

        social_res: SocialPostDeploymentResult | None = None
        try:
            if dispatch.channel in self._ads_adapters:
                raw_res = await self._ads_adapters[dispatch.channel].apply_action(dispatch.payload)

                campaign_id = str(raw_res.get("campaign_id") or dispatch.payload.get("campaign_id") or uuid.uuid4())
                budget_val = (
                    raw_res.get("applied_budget")
                    or dispatch.payload.get("budget")
                    or dispatch.payload.get("daily_budget")
                    or dispatch.payload.get("spend_amount")
                )
                try:
                    budget_float = float(budget_val) if budget_val is not None else None
                except (ValueError, TypeError):
                    budget_float = None

                bid_val = (
                    raw_res.get("applied_bid")
                    or dispatch.payload.get("bid_amount")
                    or dispatch.payload.get("bid_target")
                    or dispatch.payload.get("target_cpa")
                )
                try:
                    bid_float = float(bid_val) if bid_val is not None else None
                except (ValueError, TypeError):
                    bid_float = None

                creative_refs = raw_res.get("creative_refs") or dispatch.payload.get("creative_refs") or []
                if isinstance(creative_refs, str):
                    creative_refs = [creative_refs]

                paid_res = PaidCampaignDeploymentResult(
                    deployment_id=str(uuid.uuid4()),
                    dispatch_id=dispatch.dispatch_id,
                    task_id=dispatch.task_id,
                    tenant_id=dispatch.tenant_id,
                    channel=dispatch.channel,
                    action_type=dispatch.action_type,
                    campaign_id=campaign_id,
                    status_code=str(raw_res.get("status_code", "200")),
                    status=str(raw_res.get("status", "published")),
                    applied_budget=budget_float,
                    applied_bid=bid_float,
                    creative_refs=[str(r) for r in creative_refs],
                    provider_response=raw_res.get("provider_response", raw_res),
                    details={"raw_response": raw_res},
                )
                res = raw_res
            elif dispatch.channel in self._social_adapters:
                raw_res = await self._social_adapters[dispatch.channel].publish(dispatch.payload)

                post_id = str(
                    raw_res.get("post_id")
                    or raw_res.get("video_id")
                    or raw_res.get("publish_id")
                    or dispatch.payload.get("post_id")
                    or uuid.uuid4()
                )
                status = str(
                    raw_res.get("status")
                    or ("scheduled" if dispatch.payload.get("scheduled_at") else "published")
                )
                media_assets = (
                    raw_res.get("media_asset_ids")
                    or dispatch.payload.get("media_asset_ids")
                    or []
                )
                if isinstance(media_assets, str):
                    media_assets = [media_assets]

                social_res = SocialPostDeploymentResult(
                    deployment_id=str(uuid.uuid4()),
                    dispatch_id=dispatch.dispatch_id,
                    task_id=dispatch.task_id,
                    tenant_id=dispatch.tenant_id,
                    channel=dispatch.channel,
                    action_type=dispatch.action_type,
                    post_id=post_id,
                    status_code=str(raw_res.get("status_code", "200")),
                    status=status,
                    content_hash=dispatch.preview_content_hash,
                    media_asset_ids=[str(m) for m in media_assets],
                    provider_response=raw_res.get("provider_response", raw_res),
                    details={"raw_response": raw_res},
                )
                res = raw_res
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

                raw_items = cms_raw.get("applied_items")
                if isinstance(raw_items, list):
                    applied_items: list[dict[str, Any]] = [
                        item if isinstance(item, dict) else {"item": str(item)} for item in raw_items
                    ]
                elif isinstance(raw_items, dict):
                    applied_items = [raw_items]
                else:
                    applied_items = [cms_raw]

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
                if dispatch.channel in self._ads_adapters:
                    task_state.cts_state["paid_campaign"] = res
                elif dispatch.channel in self._social_adapters:
                    task_state.cts_state["social_post"] = (
                        social_res.model_dump() if social_res else res
                    )
                task_state.cts_state["deployment"] = res
                await self._task_state_service.save_state(dispatch.tenant_id, task_state)
                if task_state.status == TaskStatus.DISPATCHED:
                    await self._task_state_service.transition(
                        dispatch.tenant_id,
                        task_state,
                        TaskStatus.COMPLETED,
                        note=f"Successfully actuated {dispatch.channel} directive {dispatch.dispatch_id}",
                    )

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
            # Check for ambiguous timeout: attempt reconciliation before retrying or failing
            import httpx
            if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
                adapter = (
                    self._ads_adapters.get(dispatch.channel)
                    or self._social_adapters.get(dispatch.channel)
                    or (self._cms_client if dispatch.channel in ("cms", "website", "web_store") else None)
                )
                reconciled = None
                if adapter is not None and hasattr(adapter, "reconcile"):
                    try:
                        reconciled = await adapter.reconcile(dispatch.payload, idempotency_key=idempotency_key)
                    except TypeError:
                        try:
                            reconciled = await adapter.reconcile(idempotency_key)
                        except Exception:
                            reconciled = None
                    except Exception:
                        reconciled = None

                if reconciled is not None:
                    self._execution_records[idempotency_key] = reconciled
                    if self._task_state_service and dispatch.task_id and task_state:
                        try:
                            await self._task_state_service.transition(
                                dispatch.tenant_id,
                                task_state,
                                TaskStatus.COMPLETED,
                                note=f"Reconciled timeout on channel {dispatch.channel} via provider lookup",
                            )
                        except Exception:
                            pass
                    return reconciled

                # Ambiguous outcome unreconciled: mark task HELD to prevent blind duplicate actuation
                if self._task_state_service and dispatch.task_id and task_state:
                    try:
                        await self._task_state_service.transition(
                            dispatch.tenant_id,
                            task_state,
                            TaskStatus.HELD,
                            note=f"Actuation timeout on channel {dispatch.channel}; held for reconciliation: {exc}",
                        )
                    except Exception:
                        pass
                self._execution_records[idempotency_key] = {
                    "status": "AMBIGUOUS_TIMEOUT",
                    "error": str(exc),
                    "idempotency_key": idempotency_key,
                    "requires_reconciliation": True,
                }
                if self._provenance_recorder:
                    await self._provenance_recorder.record(
                        tenant_id=dispatch.tenant_id,
                        entity_id=dispatch.dispatch_id,
                        activity=f"outbound_{dispatch.channel}_timeout_reconciliation_held",
                        agent="mcp_act_boundary",
                        metadata={"error": str(exc), "idempotency_key": idempotency_key},
                    )
                raise

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
                err_metadata = scrub_sensitive_payload({
                    "error": str(exc),
                    "channel": dispatch.channel,
                    "payload": dispatch.payload,
                })
                await self._provenance_recorder.record(
                    tenant_id=dispatch.tenant_id,
                    entity_id=dispatch.dispatch_id,
                    activity=f"outbound_{dispatch.channel}_deployment_failed",
                    agent="mcp_act_boundary",
                    metadata=err_metadata,
                )
            raise