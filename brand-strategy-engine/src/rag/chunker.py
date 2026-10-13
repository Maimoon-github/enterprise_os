"""Semantic sliding-window chunker preserving structural headings and provenance."""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List


class DocumentChunker:
    """Chunks parsed text blocks into overlapping token windows with provenance tags."""

    def __init__(self, chunk_size_tokens: int = 512, overlap_tokens: int = 64):
        self.chunk_size_words = chunk_size_tokens  # heuristic 1 word ~= 1 token
        self.overlap_words = overlap_tokens

    def chunk_section(
        self,
        section: Dict[str, Any],
        document_id: str,
    ) -> List[Dict[str, Any]]:
        """Splits a single document section into overlapping chunks."""
        content = section.get("content", "")
        words = content.split()
        if not words:
            return []

        chunks: List[Dict[str, Any]] = []
        step = max(1, self.chunk_size_words - self.overlap_words)
        total_len = len(words)
        char_offset = 0

        for i in range(0, total_len, step):
            window_words = words[i : i + self.chunk_size_words]
            chunk_text = " ".join(window_words)

            # Calculate SHA256 of chunk content
            content_bytes = chunk_text.encode("utf-8")
            sha256_hash = hashlib.sha256(content_bytes).hexdigest()
            chunk_id = f"chk_{sha256_hash[:8]}"

            start_byte = char_offset
            end_byte = char_offset + len(content_bytes)
            char_offset += len(" ".join(words[i : i + step]).encode("utf-8")) + 1

            chunk_meta = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "source_filename": section.get("source_filename", "unknown"),
                "sha256_hash": sha256_hash,
                "page_number": section.get("page_number", 1),
                "section_heading": section.get("section_heading", "General"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "byte_range": [start_byte, end_byte],
                "content": chunk_text,
            }
            chunks.append(chunk_meta)

            if i + self.chunk_size_words >= total_len:
                break

        return chunks

    def chunk_document(
        self,
        sections: List[Dict[str, Any]],
        document_id: str,
    ) -> List[Dict[str, Any]]:
        """Processes all sections of a document into chunked units."""
        all_chunks: List[Dict[str, Any]] = []
        for sec in sections:
            all_chunks.extend(self.chunk_section(sec, document_id))
        return all_chunks
