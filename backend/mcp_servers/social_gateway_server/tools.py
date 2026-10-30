def execute_platform_publish(platform: str, payload: dict, idempotency_key: str) -> dict:
    return {"status": "published", "platform": platform, "idempotency_key": idempotency_key}
