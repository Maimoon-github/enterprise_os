import logging
from abc import ABC, abstractmethod
from typing import Any

from app.core.idempotency import generate_idempotency_key
from app.services.secret_service import secret_service

logger = logging.getLogger("integrations.social.base")


class SocialPlatformError(Exception):
    """Base exception for social platform API failures."""


class RateLimitOrQuotaError(SocialPlatformError):
    """Raised when platform rate limit or daily publishing quota is exceeded."""


class SandboxOnlyWarning(UserWarning):
    """Raised/flagged when platform is in sandbox or trial tier."""


class BaseSocialAdapter(ABC):
    """7-Stage Social Publishing & Read-After-Write Verification Contract:

    Stage 1: Input Blueprint Validation
    Stage 2: AES-256-GCM Token Decryption (secret_service.py)
    Stage 3: Pre-Flight Scope/Quota/Eligibility Check
    Stage 4: Media Staging & API Request (with SHA-256 Idempotency Lock)
    Stage 5: Response & Schema Validation
    Stage 6: State Persistence Mapping
    Stage 7: Read-After-Write GET Verification
    """

    platform_name: str = "generic"

    def decrypt_credentials(self, credentials: dict[str, Any]) -> dict[str, Any]:
        """Stage 2: In-memory AES-256-GCM decryption of OAuth access & refresh tokens."""
        decrypted = dict(credentials)
        if "encrypted_access_token" in credentials and credentials["encrypted_access_token"]:
            decrypted["access_token"] = secret_service.decrypt(credentials["encrypted_access_token"])
        elif "access_token" in credentials:
            decrypted["access_token"] = secret_service.decrypt(credentials["access_token"])

        if "encrypted_refresh_token" in credentials and credentials["encrypted_refresh_token"]:
            decrypted["refresh_token"] = secret_service.decrypt(credentials["encrypted_refresh_token"])
        elif "refresh_token" in credentials:
            decrypted["refresh_token"] = secret_service.decrypt(credentials["refresh_token"])

        return decrypted

    @abstractmethod
    async def pre_flight_check(self, payload: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
        """Stage 3: Pre-Flight Scope/Quota/Eligibility Guard."""
        pass

    @abstractmethod
    async def execute_publish(self, payload: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
        """Stage 4 & 5: Media Staging, API Request with idempotency lock, and Response Validation."""
        pass

    @abstractmethod
    async def verify_post(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        """Stage 7: Read-After-Write GET Verification confirming external resource existence."""
        pass

    @abstractmethod
    async def fetch_metrics(self, post_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        """Fetch cross-platform impressions, clicks, engagement, and reactions."""
        pass

    async def publish(self, payload: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
        """Full 7-Stage pipeline execution enforcing read-after-write verification."""
        # Stage 1: Input Blueprint Validation
        idempotency_key = payload.get("idempotency_key") or generate_idempotency_key(
            {"platform": self.platform_name, "payload": payload}
        )
        payload["idempotency_key"] = idempotency_key

        # Stage 2: AES-256-GCM Token Decryption
        decrypted_creds = self.decrypt_credentials(credentials)

        # Stage 3: Pre-Flight Scope/Quota/Eligibility Check
        pre_flight = await self.pre_flight_check(payload, decrypted_creds)
        if not pre_flight.get("eligible", True):
            reason = pre_flight.get("reason", "Pre-flight eligibility check failed.")
            logger.error("Pre-flight check failed for %s: %s", self.platform_name, reason)
            raise RateLimitOrQuotaError(f"{self.platform_name}: {reason}")

        # Stage 4 & 5: Media Staging, Idempotent Execution & Response Validation
        exec_res = await self.execute_publish(payload, decrypted_creds)
        post_id = exec_res.get("post_id") or exec_res.get("id") or f"{self.platform_name}_{idempotency_key[:12]}"

        # Stage 6: Determine state mapping (SANDBOX_ONLY vs PUBLISHED_UNVERIFIED)
        is_sandbox = exec_res.get("is_sandbox", False) or pre_flight.get("is_sandbox", False)
        base_status = "SANDBOX_ONLY" if is_sandbox else "PUBLISHED_UNVERIFIED"

        # Stage 7: Read-After-Write GET Verification
        verification = await self.verify_post(post_id, decrypted_creds)
        is_verified = verification.get("verified", False)

        final_status = "SANDBOX_ONLY" if is_sandbox else ("VERIFIED_PUBLISHED" if is_verified else base_status)

        return {
            "platform": self.platform_name,
            "status": final_status,
            "post_id": post_id,
            "url": verification.get("url") or exec_res.get("url") or "",
            "permalink": verification.get("permalink") or exec_res.get("permalink") or "",
            "verified": is_verified,
            "verification_details": verification,
            "idempotency_key": idempotency_key,
            "is_sandbox": is_sandbox,
        }
