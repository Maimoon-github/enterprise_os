# File: agentic_rag.py
"""
Production-grade Agentic Retrieval-Augmented Generation (Agentic RAG) Engine.

Architecture:
User Query -> Plan/Route -> Retrieve -> Evaluate -> Refine/Corrective Loops -> Grounded Synthesis

Capabilities:
1. Query Routing & Decomposition: Intent classification, multi-hop query decomposition, store routing.
2. Dynamic Multi-Source Retrieval: Dense vector similarity, sparse lexical keyword matching, structured SQL catalog.
3. Access Control & Governance: Retrieval-time tenant isolation, sensitivity ceilings, cryptographic hash checks.
4. Corrective RAG (CRAG) & Self-RAG Loops: Relevance scoring, sufficiency coverage, freshness validation, conflict detection, query rewriting, sub-query refinement, store fallback.
5. Grounded Synthesis & Citations: Strict evidence-grounded generation, inline citations, W3C PROV provenance tracing, refusal on ungrounded/conflicting/stale data.
6. Execution Ledger: Token budget limits, cost calculation, timeout bounds, iteration bounds, circuit breakers.
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("agentic_rag")


# ============================================================================
# 1. DOMAIN ENUMS, METRIC TYPES, AND SCHEMAS
# ============================================================================

class SensitivityLevel(enum.IntEnum):
    PUBLIC = 1
    INTERNAL = 2
    CONFIDENTIAL = 3
    RESTRICTED = 4


class FreshnessStatus(str, enum.Enum):
    CURRENT = "current"
    STALE = "stale"
    HISTORICAL = "historical"
    UNVERIFIED = "unverified"


class RetrievalStatus(str, enum.Enum):
    AUTHORIZED = "authorized"
    PARTIAL = "partial"
    DENIED = "denied"
    STALE = "stale"
    CONFLICTING = "conflicting"
    UNAVAILABLE = "unavailable"
    NO_MATCH = "no_match"


class EvaluationAction(str, enum.Enum):
    PROCEED_TO_SYNTHESIS = "proceed_to_synthesis"
    REWRITE_QUERY = "rewrite_query"
    DECOMPOSE_SUBQUERY = "decompose_subquery"
    FALLBACK_STORE = "fallback_store"
    ESCALATE_OR_HALT = "escalate_or_halt"


class SynthesisStatus(str, enum.Enum):
    GROUNDED = "grounded"
    PARTIAL = "partial"
    REFUSAL_INSUFFICIENT_EVIDENCE = "refusal_insufficient_evidence"
    REFUSAL_POLICY_DENIED = "refusal_policy_denied"
    REFUSAL_STALE_EVIDENCE = "refusal_stale_evidence"
    FAILED = "failed"


@dataclass(frozen=True)
class TaskContract:
    """Immutable governance contract defining identity, tenant scope, and execution bounds."""
    tenant_id: str
    brand_id: str
    requester_id: str
    purpose: str
    permitted_domains: Set[str]
    sensitivity_ceiling: SensitivityLevel = SensitivityLevel.INTERNAL
    freshness_target: Optional[datetime] = None
    max_freshness_age_seconds: Optional[float] = None
    max_iterations: int = 3
    token_budget: int = 8192
    cost_usd_budget: float = 0.50
    timeout_seconds: float = 30.0


@dataclass
class EvidenceChunk:
    """Retrievable evidence object carrying mandatory provenance and access metadata."""
    chunk_id: str
    source_uri: str
    source_authority: str
    tenant_id: str
    domain: str
    content: str
    classification: SensitivityLevel
    version: str
    effective_timestamp: datetime
    observed_timestamp: datetime
    indexed_timestamp: datetime
    provenance_hash: str
    relevance_score: float = 0.0
    freshness_status: FreshnessStatus = FreshnessStatus.UNVERIFIED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def verify_hash(self) -> bool:
        computed = compute_content_hash(self.content, self.source_uri, self.version)
        return self.provenance_hash == computed


@dataclass
class Citation:
    citation_id: str
    chunk_id: str
    source_uri: str
    source_authority: str
    quoted_text: str
    relevance_score: float
    provenance_hash: str


@dataclass
class EvaluationResult:
    is_relevant: bool
    is_sufficient: bool
    is_fresh: bool
    has_conflicts: bool
    relevance_score: float
    suggested_action: EvaluationAction
    conflicts: List[str] = field(default_factory=list)
    reasoning: str = ""
    suggested_refinements: List[str] = field(default_factory=list)


@dataclass
class GroundedAnswer:
    answer: str
    status: SynthesisStatus
    citations: List[Citation]
    confidence_score: float
    unresolved_conflicts: List[str]
    iterations_used: int
    tokens_consumed: int
    cost_usd: float
    execution_time_seconds: float
    provenance_chain: List[Dict[str, Any]]
    trace_events: List[Dict[str, Any]]


# ============================================================================
# 2. PROVENANCE, HASHING, AND METRICS UTILITIES
# ============================================================================

def compute_content_hash(content: str, source_uri: str, version: str) -> str:
    raw = f"{source_uri}::{version}::{content.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ExecutionLedger:
    """Stateful runtime tracker enforcing token, cost, iteration, and timeout bounds."""

    def __init__(self, contract: TaskContract):
        self.contract = contract
        self.start_time = time.monotonic()
        self.iterations = 0
        self.tokens_used = 0
        self.cost_usd = 0.0
        self.circuit_broken = False
        self.break_reason = ""
        self.events: List[Dict[str, Any]] = []

    def record_event(self, action: str, details: Dict[str, Any]) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - self.start_time, 4),
            "iteration": self.iterations,
            "action": action,
            "details": details,
        }
        self.events.append(event)
        logger.debug("Execution event: %s | %s", action, details)

    def consume_tokens(self, prompt_tokens: int, completion_tokens: int,
                       cost_per_1k_input: float = 0.003, cost_per_1k_output: float = 0.015) -> None:
        tokens = prompt_tokens + completion_tokens
        self.tokens_used += tokens
        incremental_cost = (prompt_tokens / 1000.0 * cost_per_1k_input) + (completion_tokens / 1000.0 * cost_per_1k_output)
        self.cost_usd += incremental_cost
        self.record_event("token_consumption", {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": self.tokens_used,
            "total_cost_usd": round(self.cost_usd, 6),
        })
        self.check_bounds()

    def check_bounds(self) -> None:
        elapsed = time.monotonic() - self.start_time
        if elapsed > self.contract.timeout_seconds:
            self.circuit_broken = True
            self.break_reason = f"Timeout exceeded: {elapsed:.2f}s > {self.contract.timeout_seconds}s"
        elif self.tokens_used > self.contract.token_budget:
            self.circuit_broken = True
            self.break_reason = f"Token budget exhausted: {self.tokens_used} > {self.contract.token_budget}"
        elif self.cost_usd > self.contract.cost_usd_budget:
            self.circuit_broken = True
            self.break_reason = f"Cost budget exhausted: ${self.cost_usd:.4f} > ${self.contract.cost_usd_budget:.4f}"
        elif self.iterations > self.contract.max_iterations:
            self.circuit_broken = True
            self.break_reason = f"Max iterations reached: {self.iterations} > {self.contract.max_iterations}"

        if self.circuit_broken:
            logger.warning("Circuit breaker activated: %s", self.break_reason)


# ============================================================================
# 3. ACCESS CONTROL AND BOUNDED RETRIEVAL BOUNDARY
# ============================================================================

class RetrievalAccessController:
    """
    Enforces authorization, tenant isolation, domain restrictions,
    and freshness policies at the retrieval boundary before model context ingress.
    """

    @staticmethod
    def filter_chunk(chunk: EvidenceChunk, contract: TaskContract) -> Tuple[bool, Optional[str]]:
        # 1. Tenant Partitioning Check (Mandatory Isolation)
        if chunk.tenant_id != contract.tenant_id:
            return False, f"Tenant mismatch: chunk tenant '{chunk.tenant_id}' != contract tenant '{contract.tenant_id}'"

        # 2. Permitted Domain Verification
        if chunk.domain not in contract.permitted_domains:
            return False, f"Domain unauthorized: '{chunk.domain}' not in {contract.permitted_domains}"

        # 3. Sensitivity Ceiling Check
        if chunk.classification > contract.sensitivity_ceiling:
            return False, f"Sensitivity ceiling violated: chunk level {chunk.classification.name} > ceiling {contract.sensitivity_ceiling.name}"

        # 4. Cryptographic Provenance Verification
        if not chunk.verify_hash():
            return False, "Provenance hash verification failed: content mismatch detected"

        return True, None

    @staticmethod
    def evaluate_freshness(chunk: EvidenceChunk, contract: TaskContract) -> FreshnessStatus:
        now = datetime.now(timezone.utc)
        effective = chunk.effective_timestamp

        if effective.tzinfo is None:
            effective = effective.replace(tzinfo=timezone.utc)

        if contract.freshness_target:
            target = contract.freshness_target
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            if effective < target:
                return FreshnessStatus.STALE

        if contract.max_freshness_age_seconds is not None:
            age = (now - effective).total_seconds()
            if age > contract.max_freshness_age_seconds:
                return FreshnessStatus.STALE

        return FreshnessStatus.CURRENT


# ============================================================================
# 4. MULTI-SOURCE RETRIEVAL STORES & PROTOCOLS
# ============================================================================

class BaseKnowledgeStore:
    def search(self, query: str, contract: TaskContract, top_k: int = 5) -> List[EvidenceChunk]:
        raise NotImplementedError


class InMemoryVectorStore(BaseKnowledgeStore):
    """Semantic vector store simulation using token overlap cosine metric."""

    def __init__(self):
        self._chunks: List[EvidenceChunk] = []

    def add_chunk(self, chunk: EvidenceChunk) -> None:
        self._chunks.append(chunk)

    def search(self, query: str, contract: TaskContract, top_k: int = 5) -> List[EvidenceChunk]:
        query_tokens = set(re.findall(r"\w+", query.lower()))
        results: List[Tuple[float, EvidenceChunk]] = []

        for chunk in self._chunks:
            allowed, _ = RetrievalAccessController.filter_chunk(chunk, contract)
            if not allowed:
                continue

            chunk_tokens = set(re.findall(r"\w+", chunk.content.lower()))
            if not chunk_tokens or not query_tokens:
                score = 0.0
            else:
                intersection = query_tokens.intersection(chunk_tokens)
                score = len(intersection) / math.sqrt(len(query_tokens) * len(chunk_tokens))

            if chunk.domain.lower() in query.lower():
                score = min(1.0, score + 0.15)

            if score > 0.05:
                chunk.relevance_score = round(score, 4)
                chunk.freshness_status = RetrievalAccessController.evaluate_freshness(chunk, contract)
                results.append((score, chunk))

        results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in results[:top_k]]


class StructuredCatalogStore(BaseKnowledgeStore):
    """Tabular database query tool simulating row-level tenant security and schema checks."""

    def __init__(self):
        self._records: List[Dict[str, Any]] = []

    def add_record(self, record: Dict[str, Any]) -> None:
        self._records.append(record)

    def search(self, query: str, contract: TaskContract, top_k: int = 5) -> List[EvidenceChunk]:
        chunks: List[EvidenceChunk] = []
        tokens = set(re.findall(r"\w+", query.lower()))

        for rec in self._records:
            if rec.get("tenant_id") != contract.tenant_id:
                continue
            if rec.get("domain") not in contract.permitted_domains:
                continue

            content = f"SKU: {rec.get('sku')} | Name: {rec.get('name')} | Specs: {rec.get('specs')} | Compliance: {rec.get('compliance')}"
            rec_tokens = set(re.findall(r"\w+", content.lower()))
            overlap = len(tokens.intersection(rec_tokens))

            if overlap > 0:
                uri = f"sql://catalog/{rec.get('tenant_id')}/{rec.get('sku')}"
                ver = str(rec.get("version", "1.0"))
                h = compute_content_hash(content, uri, ver)
                now = datetime.now(timezone.utc)
                chunk = EvidenceChunk(
                    chunk_id=f"sql_{rec.get('sku')}",
                    source_uri=uri,
                    source_authority="CatalogDatabase",
                    tenant_id=contract.tenant_id,
                    domain=rec.get("domain", "product"),
                    content=content,
                    classification=SensitivityLevel(rec.get("classification", SensitivityLevel.INTERNAL)),
                    version=ver,
                    effective_timestamp=rec.get("effective_timestamp", now),
                    observed_timestamp=now,
                    indexed_timestamp=now,
                    provenance_hash=h,
                    relevance_score=round(overlap / len(tokens), 4),
                    freshness_status=FreshnessStatus.CURRENT,
                    metadata=rec
                )
                allowed, _ = RetrievalAccessController.filter_chunk(chunk, contract)
                if allowed:
                    chunks.append(chunk)

        chunks.sort(key=lambda x: x.relevance_score, reverse=True)
        return chunks[:top_k]


class SparseKeywordStore(BaseKnowledgeStore):
    """Sparse keyword search store for exact term matching."""

    def __init__(self):
        self._chunks: List[EvidenceChunk] = []

    def add_chunk(self, chunk: EvidenceChunk) -> None:
        self._chunks.append(chunk)

    def search(self, query: str, contract: TaskContract, top_k: int = 5) -> List[EvidenceChunk]:
        query_words = [w.lower() for w in re.findall(r"\w+", query)]
        results: List[Tuple[float, EvidenceChunk]] = []

        for chunk in self._chunks:
            allowed, _ = RetrievalAccessController.filter_chunk(chunk, contract)
            if not allowed:
                continue

            content_lower = chunk.content.lower()
            words_in_content = set(re.findall(r"[A-Za-z0-9_-]+", content_lower))
            score = sum(1.0 for w in query_words if w in words_in_content)

            if score > 0:
                normalized_score = round(score / max(1, len(query_words)), 4)
                chunk.relevance_score = normalized_score
                chunk.freshness_status = RetrievalAccessController.evaluate_freshness(chunk, contract)
                results.append((normalized_score, chunk))

        results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in results[:top_k]]


class MultiSourceRetrievalBroker:
    """Mediated capability router managing multiple heterogeneous data gateways."""

    def __init__(self, vector_store: BaseKnowledgeStore, catalog_store: BaseKnowledgeStore,
                 sparse_store: Optional[BaseKnowledgeStore] = None):
        self.vector_store = vector_store
        self.catalog_store = catalog_store
        self.sparse_store = sparse_store

    def route_and_retrieve(self, sub_queries: List[str], target_stores: Set[str],
                           contract: TaskContract, ledger: ExecutionLedger) -> List[EvidenceChunk]:
        aggregated: Dict[str, EvidenceChunk] = {}

        for q in sub_queries:
            ledger.record_event("retrieval_dispatch", {"query": q, "stores": list(target_stores)})
            chunks: List[EvidenceChunk] = []

            if "vector" in target_stores or "evidence" in target_stores:
                chunks.extend(self.vector_store.search(q, contract, top_k=4))
            if "catalog" in target_stores or "sql" in target_stores:
                chunks.extend(self.catalog_store.search(q, contract, top_k=3))
            if "sparse" in target_stores and self.sparse_store is not None:
                chunks.extend(self.sparse_store.search(q, contract, top_k=3))

            for c in chunks:
                if c.chunk_id not in aggregated or c.relevance_score > aggregated[c.chunk_id].relevance_score:
                    aggregated[c.chunk_id] = c

        return list(aggregated.values())


# ============================================================================
# 5. QUERY PLANNER, EVALUATOR, AND GROUNDED SYNTHESIS ENGINE
# ============================================================================

class AgenticQueryPlanner:
    """Deconstructs complex prompts into multi-hop sub-queries and assigns target stores."""

    @staticmethod
    def plan(query: str, contract: TaskContract, ledger: ExecutionLedger) -> Tuple[List[str], Set[str]]:
        ledger.consume_tokens(prompt_tokens=180, completion_tokens=70)

        cleaned = query.strip()
        sub_queries: List[str] = []
        target_stores: Set[str] = {"vector"}

        conjunction_split = re.split(r"\b(?:and also|additionally|compare with|verify if|as well as)\b", cleaned, flags=re.IGNORECASE)
        if len(conjunction_split) > 1:
            for part in conjunction_split:
                part = part.strip()
                if len(part) > 5:
                    sub_queries.append(part)
        else:
            sub_queries.append(cleaned)

        lower_q = cleaned.lower()
        if any(term in lower_q for term in ["sku", "catalog", "spec", "price", "inventory", "dimensions"]):
            target_stores.add("catalog")
        if any(term in lower_q for term in ["clinical", "claim", "study", "efficacy", "evidence", "trial"]):
            target_stores.add("evidence")
        if any(term in lower_q for term in ["exact", "keyword", "model number", "serial"]):
            target_stores.add("sparse")

        ledger.record_event("query_planned", {"sub_queries": sub_queries, "target_stores": list(target_stores)})
        return sub_queries, target_stores


class EvidenceEvaluator:
    """
    Self-RAG and Corrective RAG (CRAG) inspector:
    Evaluates evidence relevance, sufficiency, freshness, and cross-source contradictions.
    """

    @staticmethod
    def evaluate(query: str, evidence: List[EvidenceChunk], contract: TaskContract,
                 iteration: int, ledger: ExecutionLedger) -> EvaluationResult:
        ledger.consume_tokens(prompt_tokens=220, completion_tokens=90)

        if not evidence:
            return EvaluationResult(
                is_relevant=False,
                is_sufficient=False,
                is_fresh=True,
                has_conflicts=False,
                relevance_score=0.0,
                suggested_action=EvaluationAction.FALLBACK_STORE if iteration == 0 else EvaluationAction.ESCALATE_OR_HALT,
                reasoning="No authorized evidence matches the query criteria in targeted stores."
            )

        avg_relevance = sum(e.relevance_score for e in evidence) / len(evidence)
        high_relevance_chunks = [e for e in evidence if e.relevance_score >= 0.20]
        is_relevant = len(high_relevance_chunks) > 0 and avg_relevance >= 0.15

        stale_chunks = [e for e in evidence if e.freshness_status == FreshnessStatus.STALE]
        is_fresh = len(stale_chunks) == 0

        conflicts = EvidenceEvaluator._detect_contradictions(evidence)
        has_conflicts = len(conflicts) > 0

        query_terms = set(re.findall(r"\w+", query.lower())) - {"what", "is", "the", "and", "or", "for", "with", "how", "to", "in", "of"}
        covered_terms = set()
        for e in evidence:
            covered_terms.update(re.findall(r"\w+", e.content.lower()))
        coverage = len(query_terms.intersection(covered_terms)) / max(1, len(query_terms))
        is_sufficient = is_relevant and is_fresh and not has_conflicts and coverage >= 0.40

        if has_conflicts:
            action = EvaluationAction.ESCALATE_OR_HALT
            reason = f"Irreconcilable factual conflicts detected between sources: {'; '.join(conflicts)}"
        elif not is_fresh:
            action = EvaluationAction.FALLBACK_STORE
            reason = "Retrieved evidence violates freshness policy; routing to primary authoritative source."
        elif not is_relevant:
            action = EvaluationAction.REWRITE_QUERY if iteration < contract.max_iterations else EvaluationAction.ESCALATE_OR_HALT
            reason = "Evidence relevance score below operational threshold."
        elif not is_sufficient:
            action = EvaluationAction.DECOMPOSE_SUBQUERY if iteration < contract.max_iterations else EvaluationAction.PROCEED_TO_SYNTHESIS
            reason = f"Partial topic coverage ({coverage:.0%}); deeper sub-query retrieval recommended."
        else:
            action = EvaluationAction.PROCEED_TO_SYNTHESIS
            reason = "Evidence is verified, relevant, sufficient, and fresh."

        result = EvaluationResult(
            is_relevant=is_relevant,
            is_sufficient=is_sufficient,
            is_fresh=is_fresh,
            has_conflicts=has_conflicts,
            relevance_score=avg_relevance,
            suggested_action=action,
            conflicts=conflicts,
            reasoning=reason,
            suggested_refinements=EvidenceEvaluator._generate_refinements(query, query_terms - covered_terms)
        )
        ledger.record_event("evidence_evaluated", {
            "is_relevant": is_relevant,
            "is_sufficient": is_sufficient,
            "is_fresh": is_fresh,
            "action": action.value,
            "reasoning": reason
        })
        return result

    @staticmethod
    def _detect_contradictions(evidence: List[EvidenceChunk]) -> List[str]:
        conflicts = []
        numbers_by_subject: Dict[str, List[Tuple[str, str]]] = {}
        pattern = re.compile(r"([A-Za-z0-9_-]+)\s+(?:by|of|is|at|to)\s+(\d+(?:\.\d+)?%?)", re.IGNORECASE)

        for e in evidence:
            for subject, val in pattern.findall(e.content):
                subject_key = subject.lower()
                if subject_key not in numbers_by_subject:
                    numbers_by_subject[subject_key] = []
                numbers_by_subject[subject_key].append((val, e.source_uri))

        for subj, occurrences in numbers_by_subject.items():
            distinct_vals = {val for val, _ in occurrences}
            if len(distinct_vals) > 1:
                details = ", ".join(f"{val} in {uri}" for val, uri in occurrences)
                conflicts.append(f"Contradictory values for '{subj}': {details}")

        return conflicts

    @staticmethod
    def _generate_refinements(query: str, missing_terms: Set[str]) -> List[str]:
        if not missing_terms:
            return [f"{query} details specifications"]
        return [f"{query} {' '.join(list(missing_terms)[:3])}"]


class GroundedSynthesizer:
    """
    Synthesizes answers strictly supported by evidence with inline citations.
    Refuses to speculate when evidence is missing, stale, or conflicting.
    """

    @staticmethod
    def synthesize(query: str, evidence: List[EvidenceChunk], evaluation: EvaluationResult,
                   contract: TaskContract, ledger: ExecutionLedger) -> GroundedAnswer:
        ledger.consume_tokens(prompt_tokens=350, completion_tokens=150)
        elapsed = round(time.monotonic() - ledger.start_time, 4)

        if evaluation.has_conflicts:
            return GroundedAnswer(
                answer="Refusal to answer: Conflicting evidence detected across authorized enterprise sources. "
                       f"Details: {'; '.join(evaluation.conflicts)}",
                status=SynthesisStatus.REFUSAL_INSUFFICIENT_EVIDENCE,
                citations=[],
                confidence_score=0.0,
                unresolved_conflicts=evaluation.conflicts,
                iterations_used=ledger.iterations,
                tokens_consumed=ledger.tokens_used,
                cost_usd=round(ledger.cost_usd, 6),
                execution_time_seconds=elapsed,
                provenance_chain=ledger.events,
                trace_events=ledger.events
            )

        if not evidence or evaluation.relevance_score < 0.10:
            return GroundedAnswer(
                answer="Refusal to answer: Insufficient verified enterprise evidence found to support claims for the query.",
                status=SynthesisStatus.REFUSAL_INSUFFICIENT_EVIDENCE,
                citations=[],
                confidence_score=0.0,
                unresolved_conflicts=[],
                iterations_used=ledger.iterations,
                tokens_consumed=ledger.tokens_used,
                cost_usd=round(ledger.cost_usd, 6),
                execution_time_seconds=elapsed,
                provenance_chain=ledger.events,
                trace_events=ledger.events
            )

        if not evaluation.is_fresh:
            return GroundedAnswer(
                answer="Refusal to answer: Available records violate tenant freshness requirements and cannot be verified.",
                status=SynthesisStatus.REFUSAL_STALE_EVIDENCE,
                citations=[],
                confidence_score=0.0,
                unresolved_conflicts=[],
                iterations_used=ledger.iterations,
                tokens_consumed=ledger.tokens_used,
                cost_usd=round(ledger.cost_usd, 6),
                execution_time_seconds=elapsed,
                provenance_chain=ledger.events,
                trace_events=ledger.events
            )

        citations: List[Citation] = []
        answer_parts: List[str] = []

        for idx, chunk in enumerate(evidence, start=1):
            cite_tag = f"[{idx}]"
            citation = Citation(
                citation_id=cite_tag,
                chunk_id=chunk.chunk_id,
                source_uri=chunk.source_uri,
                source_authority=chunk.source_authority,
                quoted_text=chunk.content[:140],
                relevance_score=chunk.relevance_score,
                provenance_hash=chunk.provenance_hash
            )
            citations.append(citation)
            answer_parts.append(f"{chunk.content} {cite_tag}")

        answer_text = " ".join(answer_parts)
        confidence = min(1.0, round(evaluation.relevance_score * (1.0 if evaluation.is_sufficient else 0.75), 4))
        status = SynthesisStatus.GROUNDED if evaluation.is_sufficient else SynthesisStatus.PARTIAL

        ledger.record_event("synthesis_completed", {
            "status": status.value,
            "citations_count": len(citations),
            "confidence": confidence
        })

        return GroundedAnswer(
            answer=answer_text,
            status=status,
            citations=citations,
            confidence_score=confidence,
            unresolved_conflicts=[],
            iterations_used=ledger.iterations,
            tokens_consumed=ledger.tokens_used,
            cost_usd=round(ledger.cost_usd, 6),
            execution_time_seconds=elapsed,
            provenance_chain=ledger.events,
            trace_events=ledger.events
        )


# ============================================================================
# 6. AUTONOMOUS AGENTIC RAG ORCHESTRATOR
# ============================================================================

class AgenticRAGController:
    """
    Autonomous Control Loop:
    Query -> Plan/Decompose -> Retrieve -> Evaluate -> Refine/Correct Loop -> Grounded Synthesis
    """

    def __init__(self, retrieval_broker: MultiSourceRetrievalBroker):
        self.broker = retrieval_broker

    def execute(self, query: str, contract: TaskContract) -> GroundedAnswer:
        ledger = ExecutionLedger(contract)
        ledger.record_event("execution_started", {
            "tenant_id": contract.tenant_id,
            "purpose": contract.purpose,
            "query": query,
        })

        current_query = query
        accumulated_evidence: Dict[str, EvidenceChunk] = {}
        last_eval: Optional[EvaluationResult] = None

        while not ledger.circuit_broken:
            ledger.iterations += 1
            ledger.record_event("iteration_started", {"iteration": ledger.iterations, "query": current_query})

            # 1. Plan & Route
            sub_queries, target_stores = AgenticQueryPlanner.plan(current_query, contract, ledger)

            # 2. Retrieve via Governed Multi-Source Broker
            retrieved = self.broker.route_and_retrieve(sub_queries, target_stores, contract, ledger)
            for chunk in retrieved:
                accumulated_evidence[chunk.chunk_id] = chunk

            evidence_list = list(accumulated_evidence.values())

            # 3. Evaluate Evidence (Self-Reflection & Corrective RAG)
            eval_result = EvidenceEvaluator.evaluate(query, evidence_list, contract, ledger.iterations - 1, ledger)
            last_eval = eval_result

            # 4. Corrective Decision Loop
            if eval_result.suggested_action == EvaluationAction.PROCEED_TO_SYNTHESIS:
                break
            elif eval_result.suggested_action == EvaluationAction.REWRITE_QUERY:
                if eval_result.suggested_refinements:
                    current_query = eval_result.suggested_refinements[0]
                else:
                    current_query = f"{current_query} verified facts"
                ledger.record_event("query_rewritten", {"new_query": current_query})
            elif eval_result.suggested_action == EvaluationAction.DECOMPOSE_SUBQUERY:
                if eval_result.suggested_refinements:
                    current_query = eval_result.suggested_refinements[0]
                ledger.record_event("query_decomposed", {"decomposed_query": current_query})
            elif eval_result.suggested_action == EvaluationAction.FALLBACK_STORE:
                target_stores.add("catalog")
                ledger.record_event("store_fallback_triggered", {"stores": list(target_stores)})
            elif eval_result.suggested_action == EvaluationAction.ESCALATE_OR_HALT:
                ledger.record_event("execution_halted_by_evaluator", {"reason": eval_result.reasoning})
                break

            ledger.check_bounds()

        # 5. Final Grounded Synthesis
        if last_eval is None:
            last_eval = EvaluationResult(
                is_relevant=False, is_sufficient=False, is_fresh=False, has_conflicts=False,
                relevance_score=0.0, suggested_action=EvaluationAction.ESCALATE_OR_HALT,
                reasoning=ledger.break_reason or "Execution terminated prior to evaluation."
            )

        return GroundedSynthesizer.synthesize(
            query=query,
            evidence=list(accumulated_evidence.values()),
            evaluation=last_eval,
            contract=contract,
            ledger=ledger
        )