"""RAG search tool for domain agents to retrieve grounded user document chunks."""

from typing import Any, Dict, List, Optional


class RAGSearchTool:
    """Tool enabling domain agents to query indexed client documents and pitch decks."""

    def __init__(self, vector_store=None):
        self.vector_store = vector_store

    async def search(
        self,
        query: str,
        top_k: int = 5,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries the vector store for semantic matches with provenance metadata."""
        if not self.vector_store:
            return []

        results = await self.vector_store.query(
            query=query,
            top_k=top_k,
            tenant_id=tenant_id,
        )
        return results

    def to_params(self) -> Dict[str, Any]:
        return {
            "name": "rag_query",
            "description": "Retrieve grounded factual citations from indexed user documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query keywords or phrase"},
                    "top_k": {"type": "integer", "description": "Number of matching chunks to return"},
                },
                "required": ["query"],
            },
        }
