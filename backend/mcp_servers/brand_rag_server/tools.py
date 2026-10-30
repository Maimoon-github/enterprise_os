def search_brand_knowledge(query: str, limit: int = 5) -> list[dict]:
    return [{"content": f"Brand knowledge result for {query}", "score": 0.95}]
