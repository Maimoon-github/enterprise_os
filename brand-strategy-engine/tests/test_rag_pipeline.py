"""Tests for multi-format parser, sliding-window chunker, embedder, and vector store."""

import tempfile
from pathlib import Path
import pytest
from src.rag.chunker import DocumentChunker
from src.rag.embedder import OllamaEmbedder
from src.rag.parser import DocumentParser
from src.rag.store import VectorStore


def test_document_parser_text_and_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test plain text
        txt_file = Path(tmpdir) / "test.txt"
        txt_file.write_text("Introduction to distributed systems architecture.", encoding="utf-8")
        sections = DocumentParser.parse_file(str(txt_file))
        assert len(sections) == 1
        assert "distributed systems" in sections[0]["content"]

        # Test CSV
        csv_file = Path(tmpdir) / "metrics.csv"
        csv_file.write_text("kpi,baseline,target\ncvr,1.2%,4.5%\nbounce,65%,40%\n", encoding="utf-8")
        csv_sections = DocumentParser.parse_file(str(csv_file))
        assert len(csv_sections) >= 1
        assert "cvr" in csv_sections[1]["content"]


def test_document_chunker_provenance():
    chunker = DocumentChunker(chunk_size_tokens=10, overlap_tokens=2)
    section = {
        "source_filename": "pitch_deck.pdf",
        "page_number": 4,
        "section_heading": "Unit Economics",
        "content": "Blended customer acquisition cost increased by thirty percent during the second quarter due to landing page friction.",
    }
    chunks = chunker.chunk_section(section, document_id="doc_deck")
    assert len(chunks) >= 2

    first = chunks[0]
    assert first["chunk_id"].startswith("chk_")
    assert len(first["sha256_hash"]) == 64
    assert first["page_number"] == 4
    assert first["section_heading"] == "Unit Economics"
    assert "byte_range" in first
    assert len(first["byte_range"]) == 2


@pytest.mark.asyncio
async def test_embedder_dimension_and_norm():
    embedder = OllamaEmbedder(dimension=768)
    vec = await embedder.embed_text("Sample query for semantic retrieval")
    assert len(vec) == 768
    # Test unit length normalization (approx 1.0)
    mag = sum(x * x for x in vec) ** 0.5
    assert pytest.approx(mag, 0.05) == 1.0


@pytest.mark.asyncio
async def test_vector_store_indexing_and_query():
    embedder = OllamaEmbedder(dimension=768)
    store = VectorStore(embedder=embedder)

    sample_chunks = [
        {
            "chunk_id": "chk_001",
            "document_id": "doc_1",
            "source_filename": "guide.pdf",
            "content": "Distributed consensus algorithms like Raft and Paxos ensure replication safety.",
            "section_heading": "Consensus",
        },
        {
            "chunk_id": "chk_002",
            "document_id": "doc_1",
            "source_filename": "guide.pdf",
            "content": "High conversion Shopify store optimization focuses on checkout drop-off reduction.",
            "section_heading": "eCommerce CRO",
        },
    ]

    indexed = await store.add_chunks(sample_chunks, tenant_id="tenant_alpha")
    assert indexed == 2

    # Query for consensus
    results = await store.query("distributed consensus raft replication", top_k=1, tenant_id="tenant_alpha")
    assert len(results) == 1
    assert results[0]["chunk_id"] == "chk_001"
    assert "similarity_score" in results[0]

    # Provenance lookup
    resolved = store.get_chunk_by_id("chk_002")
    assert resolved is not None
    assert resolved["section_heading"] == "eCommerce CRO"
