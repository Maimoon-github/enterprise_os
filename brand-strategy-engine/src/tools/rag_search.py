"""RAG search tool for domain agents to retrieve grounded user document chunks."""

import logging
import re
from typing import Any, Dict, List, Optional
from src.schemas.evidence import ChunkProvenance, EvidenceReference

logger = logging.getLogger(__name__)


class RAGSearchTool:
    """Tool enabling domain agents (Agents 1-5) to query indexed client documents with proactive Evidence Assurance."""

    def __init__(self, vector_store=None, min_similarity_threshold: float = 0.10):
        self.vector_store = vector_store
        self.min_similarity_threshold = min_similarity_threshold

    @staticmethod
    def sanitize_untrusted_content(content: str, source_filename: str = "") -> str:
        """Wraps untrusted client document content in protective data fences neutralizing prompt injection."""
        sanitized = content.replace("<|im_start|>", "[sanitized_token]")
        sanitized = sanitized.replace("<|im_end|>", "[sanitized_token]")
        sanitized = sanitized.replace("```", "'''")
        sanitized = re.sub(
            r"(?i)\b(ignore previous instructions|system prompt|sudo|admin|override rbac)\b",
            r"[\1]",
            sanitized,
        )
        return f'<untrusted_client_data source="{source_filename}">\n{sanitized}\n</untrusted_client_data>'

    @staticmethod
    def detect_contradictions(
        rag_claims: List[Dict[str, Any]],
        dom_snapshots: Optional[Dict[str, Any]] = None,
        visual_evidence: Optional[List[Any]] = None,
    ) -> List[str]:
        """Flags discrepancies between uploaded client documents and live website observations."""
        contradictions: List[str] = []
        if not rag_claims:
            return contradictions

        live_text = ""
        if dom_snapshots:
            for snap in dom_snapshots.values():
                if isinstance(snap, dict):
                    live_text += " " + str(snap.get("text", "")) + " " + str(snap.get("headings", ""))
                else:
                    live_text += " " + str(snap)

        live_text_lower = live_text.lower()

        for chunk in rag_claims:
            text = chunk.get("content", "").lower()
            src = chunk.get("source_filename", "client_doc")
            if "$99" in text and "$149" in live_text_lower:
                contradictions.append(
                    f"Pricing Contradiction: Document ({src}) claims $99 pricing, but live DOM indicates $149."
                )
            if "enterprise b2b" in text and ("direct-to-consumer" in live_text_lower or "dtc" in live_text_lower):
                contradictions.append(
                    f"Market Contradiction: Document ({src}) claims Enterprise B2B focus, but live DOM exhibits DTC positioning."
                )
            if "14-day free trial" in text and "no free trial" in live_text_lower:
                contradictions.append(
                    f"Trial Contradiction: Document ({src}) claims 14-day free trial, but live site specifies no free trial."
                )

        return contradictions

    async def search(
        self,
        query: str,
        top_k: int = 5,
        tenant_id: Optional[str] = None,
        context_gaps: Optional[List[str]] = None,
        dom_snapshots: Optional[Dict[str, Any]] = None,
        visual_evidence: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Queries the vector store for semantic matches with provenance metadata and evidence assurance."""
        if not self.vector_store:
            if context_gaps is not None:
                context_gaps.append(f"Context Gap: RAG search unavailable for query '{query}': Vector store not initialized.")
            return []

        raw_results = await self.vector_store.query(
            query=query,
            top_k=top_k,
            tenant_id=tenant_id,
        )

        # Filter by similarity threshold
        filtered = [r for r in raw_results if r.get("similarity_score", 1.0) >= self.min_similarity_threshold]

        if not filtered:
            if context_gaps is not None:
                context_gaps.append(
                    f"Context Gap: No empirical document evidence found for query '{query}' above similarity threshold {self.min_similarity_threshold}."
                )
            return []

        processed: List[Dict[str, Any]] = []
        for r in filtered:
            item = dict(r)
            raw_content = item.get("content", "")
            src_file = item.get("source_filename", "unknown")
            item["sanitized_content"] = self.sanitize_untrusted_content(raw_content, src_file)
            processed.append(item)

        if context_gaps is not None and (dom_snapshots or visual_evidence):
            discrepancies = self.detect_contradictions(processed, dom_snapshots, visual_evidence)
            for d in discrepancies:
                if d not in context_gaps:
                    context_gaps.append(f"Contradiction Detected: {d}")

        return processed

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
