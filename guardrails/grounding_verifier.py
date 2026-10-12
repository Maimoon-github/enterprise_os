# pyright: reportMissingImports=false
"""Anti-Hallucination and Proof Grounding Verifier (TSK-06).
Cross-verifies factual claims, product specifications, and numerical metrics against verified RAG chunks.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ClaimVerification(BaseModel):
    """Verification record for a specific factual claim extracted from copy."""

    claim: str
    is_grounded: bool
    source_chunk_id: Optional[str] = None
    confidence_score: float = 0.0
    citation: str = ""
    evidence_snippet: str = ""


class GroundingVerificationResult(BaseModel):
    """Aggregate result from anti-hallucination grounding verification."""

    is_grounded: bool
    total_claims_count: int = 0
    grounded_claims_count: int = 0
    citation_coverage: float = 1.0  # 0.0 to 1.0
    verified_claims: List[ClaimVerification] = Field(default_factory=list)
    ungrounded_claims: List[str] = Field(default_factory=list)
    feedback: str = ""


class GroundingVerifier:
    """Cross-references assertions against verified RAG knowledge base chunks."""

    def __init__(self, min_coverage_threshold: float = 0.85):
        self.min_coverage_threshold = min_coverage_threshold

    def extract_factual_claims(self, copy_text: str) -> List[str]:
        """Extract sentences or phrases containing verifiable numerical claims, metrics, or specs."""
        claims: List[str] = []

        # Split into individual sentences (avoid splitting on decimals like $68.00)
        sentences = [s.strip() for s in re.split(r"(?<!\d)\.(?:\s+|$)|[\n!?]+", copy_text) if s.strip()]

        for s in sentences:
            # Detect numerical claims, percentages, currency, or explicit assertions
            has_metric = bool(re.search(r"\d+(?:\.\d+)?%|\$\d+(?:\.\d+)?|\b\d+\s*(?:days|weeks|months|users|clients|orders)\b", s, re.I))
            has_clinical_or_spec = bool(re.search(r"proven|clinically|guaranteed|certified|tested|niacinamide|hyaluronic|ingredient|roas|cac|clv", s, re.I))
            if has_metric or has_clinical_or_spec:
                claims.append(s)

        # Fallback: if no specific metrics detected, treat sentences with strong factual assertions
        if not claims and sentences:
            claims = [s for s in sentences if len(s.split()) >= 4][:5]

        return claims

    def verify_grounding(
        self,
        copy_text: str,
        source_chunks: List[Dict[str, Any]],
        retriever: Optional[Any] = None,
    ) -> GroundingVerificationResult:
        """Verify that every factual assertion in copy_text is supported by source_chunks or RAG store."""
        claims = self.extract_factual_claims(copy_text)
        if not claims:
            return GroundingVerificationResult(
                is_grounded=True,
                total_claims_count=0,
                grounded_claims_count=0,
                citation_coverage=1.0,
                feedback="No verifiable factual claims detected in copy.",
            )

        # Build corpus text and chunk lookup from source chunks
        normalized_chunks: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(source_chunks):
            content = str(chunk.get("content") or chunk.get("text") or chunk.get("page_content") or "")
            chunk_id = str(chunk.get("id") or chunk.get("chunk_id") or f"CHUNK-{idx:03d}")
            normalized_chunks.append({"id": chunk_id, "content": content.lower(), "raw": content})

        verified_records: List[ClaimVerification] = []
        ungrounded: List[str] = []

        for claim in claims:
            claim_lower = claim.lower()
            # Extract key nouns and numbers from claim
            tokens = set(re.findall(r"\b[A-Za-z0-9'-]{3,}\b", claim_lower))
            numbers = set(re.findall(r"\d+(?:\.\d+)?", claim_lower))

            best_match_id = None
            best_score = 0.0
            best_snippet = ""

            for chunk in normalized_chunks:
                chunk_text = chunk["content"]

                # 1. Check if specific numbers match
                num_matches = sum(1 for n in numbers if n in chunk_text) if numbers else 0
                all_numbers_grounded = (num_matches == len(numbers)) if numbers else True

                # 2. Token overlap score
                token_matches = sum(1 for t in tokens if t in chunk_text)
                token_score = token_matches / max(len(tokens), 1)

                if all_numbers_grounded and token_score > best_score:
                    best_score = token_score
                    best_match_id = chunk["id"]
                    # Extract surrounding context snippet
                    best_snippet = chunk["raw"][:160].strip() + "..."

            # Claim is grounded if numbers match and token overlap is significant (>= 0.35)
            is_claim_grounded = bool(best_match_id is not None and best_score >= 0.35)

            if is_claim_grounded and best_match_id:
                verified_records.append(
                    ClaimVerification(
                        claim=claim,
                        is_grounded=True,
                        source_chunk_id=best_match_id,
                        confidence_score=round(best_score, 2),
                        citation=f"Cited from [{best_match_id}]",
                        evidence_snippet=best_snippet,
                    )
                )
            else:
                verified_records.append(
                    ClaimVerification(
                        claim=claim,
                        is_grounded=False,
                        confidence_score=round(best_score, 2),
                        citation="UNGROUNDED",
                    )
                )
                ungrounded.append(claim)

        grounded_count = len([v for v in verified_records if v.is_grounded])
        total_count = len(claims)
        coverage = grounded_count / max(total_count, 1)

        is_fully_grounded = coverage >= self.min_coverage_threshold and len(ungrounded) == 0

        feedback = (
            f"Factual verification passed: {grounded_count}/{total_count} claims successfully grounded against RAG store."
            if is_fully_grounded
            else f"Verification failed: {len(ungrounded)} ungrounded claim(s) detected. Missing proof for: " + " | ".join(ungrounded[:2])
        )

        return GroundingVerificationResult(
            is_grounded=is_fully_grounded,
            total_claims_count=total_count,
            grounded_claims_count=grounded_count,
            citation_coverage=round(coverage, 2),
            verified_claims=verified_records,
            ungrounded_claims=ungrounded,
            feedback=feedback,
        )
