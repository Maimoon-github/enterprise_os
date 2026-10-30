import logging
from typing import Any

from app.core.idempotency import generate_idempotency_key
from app.orchestrator.state import PlatformType
from app.services.secret_service import SecretService
from mcp_servers.social_gateway_server.adapters import get_social_adapter

logger = logging.getLogger("mcp.social_gateway.tools")
_published_idempotency_keys: set[str] = set()


async def execute_platform_publish(
    platform: PlatformType,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
    encrypted_credentials: str | None = None,
) -> dict[str, Any]:
    """Execute social post publication via platform adapter with decrypted in-memory credentials."""
    key = idempotency_key or generate_idempotency_key({"platform": platform, "payload": payload})
    if key in _published_idempotency_keys:
        return {
            "status": "skipped_duplicate",
            "idempotency_key": key,
            "message": "Duplicate post detected; publish skipped.",
        }

    adapter = get_social_adapter(platform)

    # In-memory zero-trust credential decryption
    decrypted_token = (
        SecretService.decrypt_secret(encrypted_credentials)
        if encrypted_credentials
        else "mock_decrypted_oauth_token"
    )
    credentials = {"access_token": decrypted_token, "platform": platform}

    result = await adapter.publish(payload, credentials)
    result["idempotency_key"] = key
    _published_idempotency_keys.add(key)
    return result


async def execute_verify_post(
    platform: PlatformType,
    post_id: str,
    encrypted_credentials: str | None = None,
) -> dict[str, Any]:
    """Verify live status of a post on target platform."""
    adapter = get_social_adapter(platform)
    credentials = {"access_token": "mock_token", "platform": platform}
    return await adapter.verify_post(post_id, credentials)


async def execute_fetch_metrics(
    platform: PlatformType,
    post_id: str,
    encrypted_credentials: str | None = None,
) -> dict[str, Any]:
    """Fetch engagement metrics for a post."""
    adapter = get_social_adapter(platform)
    credentials = {"access_token": "mock_token", "platform": platform}
    return await adapter.fetch_metrics(post_id, credentials)


publish_to_platform = execute_platform_publish
verify_platform_post = execute_verify_post
fetch_platform_metrics = execute_fetch_metrics
