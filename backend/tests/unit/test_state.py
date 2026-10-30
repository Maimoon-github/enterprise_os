def test_merge_platform_results():
    from app.orchestrator.state import merge_platform_results
    existing = [{"idempotency_key": "k1", "status": "pending"}]
    new_items = [{"idempotency_key": "k1", "status": "published"}]
    merged = merge_platform_results(existing, new_items)
    assert len(merged) == 1
    assert merged[0]["status"] == "published"
