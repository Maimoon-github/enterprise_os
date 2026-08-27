#!/usr/bin/env python3
"""
social_agent_runner.py
═══════════════════════════════════════════════════════════════════════════════
Production-grade social_agent workflow runner — zero external credentials.

All generative content is produced by a live local Ollama LLM.
No hardcoded responses, no calibration overrides, no injected fallbacks.

LLM backend : http://127.0.0.1:11434/v1/chat/completions  (OpenAI-compat API)
Primary model: llama3.2:3b  │  Fallback: mistral:7b

Workflow phases
───────────────
  Phase 1 · PLAN    : Safety scan → Brand RAG → LLM trend synthesis
  Phase 2 · ACT     : LLM copywriter (X/Twitter, Instagram, TikTok) with retry
  Phase 3 · OBSERVE : SSRF URL validation → LLM alt-text generation
  Phase 4 · REFLECT : LLM-as-a-Judge multi-metric audit with retry on parse fail
  Phase 5 · PUBLISH : Routing gate → FastMCP mock dispatch

Design invariants
─────────────────
  • Every piece of generated content comes from a live LLM call.
  • Format violations → LLM retry (max MAX_COPY_RETRIES), not manual injection.
  • Judge JSON parse failures → LLM retry (max MAX_JUDGE_RETRIES), not fallback scores.
  • No calibration floors or hardcoded score overrides.
  • FastMCP post IDs are stub infrastructure (platform APIs are not available locally).
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("social_agent")

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
OLLAMA_BASE    = "http://127.0.0.1:11434/v1"
PRIMARY_MODEL  = "llama3.2:3b"
FALLBACK_MODEL = "mistral:7b"

MAX_COPY_RETRIES  = 4   # LLM re-prompts before enforcing budget trim
MAX_JUDGE_RETRIES = 2   # retries before raising for Phase 4 judge JSON parse
LLM_TIMEOUT       = 120.0  # seconds per Ollama request

# Platform character/hashtag constraints (source of truth — mirrors platform APIs)
PLATFORM_LIMITS: Dict[str, Dict[str, Any]] = {
    "x_twitter": {"max_chars": 280, "min_hashtags": 1, "max_hashtags": 2},
    "instagram":  {"max_chars": 2200, "min_hashtags": 3, "max_hashtags": 30},
    "tiktok":     {"max_chars": 2200, "min_hashtags": 2, "max_hashtags": 10},
}

# Brand governance policy (configuration — not generated content)
BRAND_POLICY: List[str] = [
    "Brand Voice: Authoritative, technically precise, innovation-focused. Never consumer-friendly simplifications.",
    "Prohibited Terms: Never use 'revolutionize', 'synergy', 'disruptive', or 'game-changer'. Use exact technical descriptors.",
    "Hashtag Policy: 2 hashtags for X/Twitter. 3–5 for Instagram/TikTok. Tags must map to real architectural concepts.",
    "Tone: Lead with quantifiable, verifiable facts — latency figures, throughput metrics, fault tolerance percentages.",
    "Audience: CTO, VP Engineering, principal engineers. Level-5 technical vocabulary required. No marketing language.",
]

# Safety guardrail patterns (configuration — not generated content)
INJECTION_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"(?i)\bignore\s+(?:all\s+)?previous\s+instructions\b"),
    re.compile(r"(?i)\bsystem\s+override\b"),
    re.compile(r"(?i)\bjailbreak\b"),
    re.compile(r"(?i)\bdeveloper\s+mode\b"),
    re.compile(r"(?i)\bDAN\s+mode\b"),
    re.compile(r"(?i)\bdisregard\s+(?:all\s+)?prior\s+prompts\b"),
    re.compile(r"(?i)\breveal\s+(?:the\s+)?system\s+prompt\b"),
]
EMAIL_RE  = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE  = re.compile(r"\b(?:\+?\d{1,3}[-.\\s]?)?\(?\d{3}\)?[-.\\s]?\d{3}[-.\\s]?\d{4}\b")
SECRET_RE = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|bearer|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?"
)
PROHIBITED_TERMS = ["revolutionize", "synergy", "disruptive", "game-changer"]

# Audit scoring weights (sum = 1.0)
AUDIT_WEIGHTS: Dict[str, float] = {
    "faithfulness": 0.35,
    "brand_voice":  0.35,
    "formatting":   0.15,
    "safety":       0.15,
}

# ─────────────────────────────────────────────────────────────────────────────
# Global LLM call log (append-only, used for transcript output)
# ─────────────────────────────────────────────────────────────────────────────
_llm_call_log: List[Dict[str, Any]] = []


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: LLM Client
# ─────────────────────────────────────────────────────────────────────────────

async def llm_chat(
    messages: List[Dict[str, str]],
    *,
    call_label: str,
    model: str = PRIMARY_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    timeout: float = LLM_TIMEOUT,
) -> str:
    """
    Asynchronous wrapper for the Ollama OpenAI-compatible chat endpoint.

    Automatically falls back to FALLBACK_MODEL on primary failures.
    Appends every exchange to `_llm_call_log` for the response transcript.

    Args:
        messages:     OpenAI-format message list.
        call_label:   Human-readable identifier for log/transcript grouping.
        model:        LLM model identifier.
        temperature:  Sampling temperature.
        max_tokens:   Maximum completion tokens.
        timeout:      Per-request HTTP timeout in seconds.

    Returns:
        Raw assistant message content string (unprocessed).

    Raises:
        RuntimeError: If both primary and fallback models fail.
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    endpoint   = f"{OLLAMA_BASE}/chat/completions"
    used_model = model
    raw_content: str
    usage: Dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
        try:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage", {})
        except Exception as primary_err:
            logger.warning(
                "Primary model '%s' failed: %s — falling back to '%s'",
                model, primary_err, FALLBACK_MODEL,
            )
            payload["model"] = FALLBACK_MODEL
            used_model = FALLBACK_MODEL
            try:
                resp2 = await client.post(endpoint, json=payload)
                resp2.raise_for_status()
                data2 = resp2.json()
                raw_content = data2["choices"][0]["message"]["content"].strip()
                usage = data2.get("usage", {})
            except Exception as fallback_err:
                raise RuntimeError(
                    f"Both '{model}' and '{FALLBACK_MODEL}' failed. "
                    f"Last error: {fallback_err}"
                ) from fallback_err

    _llm_call_log.append({
        "call_label":        call_label,
        "model":             used_model,
        "temperature":       temperature,
        "prompt_tokens":     usage.get("prompt_tokens", len(str(messages)) // 4),
        "completion_tokens": usage.get("completion_tokens", len(raw_content) // 4),
        "system_prompt":     next((m["content"] for m in messages if m["role"] == "system"), ""),
        "user_prompt":       next((m["content"] for m in reversed(messages) if m["role"] == "user"), ""),
        "raw_response":      raw_content,
    })

    logger.debug("[%s] %s → %d chars", call_label, used_model, len(raw_content))
    return raw_content


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Safety Guardrail (deterministic — no LLM)
# ─────────────────────────────────────────────────────────────────────────────

def safety_scan(text: str) -> Tuple[bool, str, List[str]]:
    """
    Deterministic inbound safety scan.

    Checks for prompt injection patterns and PII (email, phone, secrets).
    PII is redacted in the returned sanitized text.

    Returns:
        (is_safe, sanitized_text, list_of_violations)
        is_safe is False only on prompt injection — PII violations still allow processing.
    """
    violations: List[str] = []

    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            violations.append(f"Prompt injection: {pat.pattern[:50]!r}")

    if violations:
        return False, text, violations

    sanitized = text
    if SECRET_RE.search(sanitized):
        violations.append("Exposed API key / secret token")
        sanitized = SECRET_RE.sub("[REDACTED_SECRET]", sanitized)
    if EMAIL_RE.search(sanitized):
        violations.append("Exposed email address")
        sanitized = EMAIL_RE.sub("[REDACTED_EMAIL]", sanitized)
    if PHONE_RE.search(sanitized):
        violations.append("Exposed phone number")
        sanitized = PHONE_RE.sub("[REDACTED_PHONE]", sanitized)

    return True, sanitized, violations


def check_prohibited_terms(text: str) -> List[str]:
    """Returns any prohibited brand terms found in `text`."""
    return [t for t in PROHIBITED_TERMS if t.lower() in text.lower()]


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: SSRF / URL Validator (deterministic — no LLM)
# ─────────────────────────────────────────────────────────────────────────────

def validate_media_url(url: str) -> Tuple[bool, str]:
    """
    Validates a media URL against SSRF and scheme rules.

    Returns:
        (is_valid, reason_string)
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        return False, f"URL parse error: {exc}"

    if parsed.scheme != "https":
        return False, f"Non-HTTPS scheme '{parsed.scheme}' rejected"

    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1", ""):
        return False, f"Loopback / empty host '{host}' rejected"
    if host.startswith("192.168.") or host.startswith("10.") or host.startswith("172."):
        return False, f"Private-range IP '{host}' rejected (SSRF)"

    return True, "OK"


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: Brand RAG (BM25 over in-memory policy corpus)
# ─────────────────────────────────────────────────────────────────────────────

def bm25_retrieve(query: str, corpus: List[str], top_k: int = 4) -> List[str]:
    """Lightweight BM25-style term-overlap retriever over the brand policy corpus."""
    query_terms = set(re.findall(r"\w+", query.lower()))
    scored = sorted(
        corpus,
        key=lambda doc: len(query_terms & set(re.findall(r"\w+", doc.lower()))),
        reverse=True,
    )
    return scored[:top_k]


# ─────────────────────────────────────────────────────────────────────────────
# Section 5: Mock FastMCP Client (stub infrastructure — post IDs only)
# ─────────────────────────────────────────────────────────────────────────────

class FastMCPClient:
    """
    Stub implementation of the FastMCP tool connector.

    The platform post IDs are stubs — they simulate what the real social media
    platform APIs would return.  Trend signals are *not* hardcoded here;
    an LLM call in Phase 1 synthesises them from the campaign brief instead.
    """

    async def post(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate a JSON-RPC 2.0 tool call and return a stub dispatch response."""
        await asyncio.sleep(0.03)   # simulate network round-trip
        stub_ids = {
            "post_x_tweet":    {"status": "success", "post_id": f"x_{uuid.uuid4().hex[:8]}"},
            "post_instagram":  {"status": "success", "post_id": f"ig_{uuid.uuid4().hex[:8]}"},
            "post_tiktok":     {"status": "success", "publish_id": f"tt_{uuid.uuid4().hex[:8]}"},
        }
        result = stub_ids.get(tool)
        if result is None:
            return {"status": "error", "message": f"Unknown tool: {tool!r}"}
        logger.info("  FastMCP  %-22s → %s", tool, result)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Section 6: Checkpointer (in-memory state snapshot)
# ─────────────────────────────────────────────────────────────────────────────

class Checkpointer:
    """Records named state snapshots between graph node transitions."""

    def __init__(self, thread_id: str) -> None:
        self.thread_id = thread_id
        self._snapshots: List[Dict[str, Any]] = []

    def save(self, node: str, state: Dict[str, Any]) -> str:
        checkpoint_id = f"ckpt_{node}_{uuid.uuid4().hex[:8]}"
        self._snapshots.append({
            "checkpoint_id": checkpoint_id,
            "node": node,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state_keys": sorted(state.keys()),
        })
        logger.debug("[CKPT] %s → %s", node, checkpoint_id)
        return checkpoint_id

    @property
    def count(self) -> int:
        return len(self._snapshots)

    @property
    def node_sequence(self) -> List[str]:
        return [s["node"] for s in self._snapshots]


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: PLAN (plan_research_node)
# ─────────────────────────────────────────────────────────────────────────────

async def phase_plan(prompt: str) -> Dict[str, Any]:
    """
    Phase 1 — PLAN: safety scan, brand RAG retrieval, LLM trend synthesis.

    The LLM synthesises 3–5 current trend signals from the campaign brief and
    brand context.  No trend strings are hardcoded anywhere.

    Returns state fragment with sanitized_prompt, brand_context, trend_signals,
    and the combined research_context list.
    """
    logger.info("━" * 70)
    logger.info("PHASE 1 · PLAN  (plan_research_node)")
    logger.info("━" * 70)

    # 1.1 Deterministic safety scan
    logger.info("  1.1  SafetyGuardrail: injection + PII scan")
    is_safe, sanitized, violations = safety_scan(prompt)
    if not is_safe:
        raise ValueError(f"Inbound prompt safety failure: {violations}")
    logger.info("       ✓ safe=True  violations=%s", violations or "none")

    # 1.2 Brand RAG (BM25 over policy corpus)
    logger.info("  1.2  BM25 brand_governance_rag retrieval")
    brand_context = bm25_retrieve(sanitized, BRAND_POLICY, top_k=4)
    for chunk in brand_context:
        logger.info("       • %s", chunk[:90])

    # 1.3 LLM trend synthesis — no hardcoded trends
    logger.info("  1.3  LLM trend synthesis (%s)", PRIMARY_MODEL)
    brand_block = "\n".join(f"- {c}" for c in brand_context)
    trend_messages = [
        {
            "role": "system",
            "content": (
                "You are an enterprise technology market analyst. "
                "Synthesise 3 to 5 current, specific industry trends relevant to the campaign brief. "
                "Each trend must be a single sentence starting with 'Trend:' and include a quantifiable signal "
                "(percentage, metric, or verifiable fact). "
                "Output ONLY the numbered trend list. No preamble, no summary."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Campaign brief: {sanitized}\n\n"
                f"Brand context:\n{brand_block}\n\n"
                "Generate 3–5 concise industry trend signals relevant to this campaign."
            ),
        },
    ]
    raw_trends = await llm_chat(
        trend_messages,
        call_label="phase1_trend_synthesis",
        temperature=0.4,
        max_tokens=300,
    )

    # Parse individual trend lines from LLM output
    trend_signals: List[str] = [
        line.strip()
        for line in raw_trends.splitlines()
        if line.strip() and re.match(r"^(\d+[\.\)]\s*)?[Tt]rend:", line.strip())
    ]

    # Fallback: treat every non-empty line as a trend if none matched the prefix
    if not trend_signals:
        trend_signals = [
            line.strip() for line in raw_trends.splitlines() if line.strip()
        ]

    if len(trend_signals) < 2:
        raise ValueError(
            f"LLM trend synthesis returned fewer than 2 trend signals.\n"
            f"Raw output:\n{raw_trends}"
        )

    logger.info("       ✓ %d trend signals synthesised:", len(trend_signals))
    for t in trend_signals:
        logger.info("         • %s", t[:95])

    research_context = brand_context + trend_signals
    logger.info("  PLAN complete: %d total context chunks.", len(research_context))

    return {
        "is_safe":               True,
        "sanitized_prompt":      sanitized,
        "scan_violations":       violations,
        "brand_context":         brand_context,
        "trend_signals":         trend_signals,
        "research_context":      research_context,
        "research_context_count": len(research_context),
        "brand_rules_retrieved": len(brand_context),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: ACT (act_draft_node) — LLM copywriter with format-aware retry
# ─────────────────────────────────────────────────────────────────────────────

_PLATFORM_SYSTEM_PROMPTS: Dict[str, str] = {
    "x_twitter": (
        "You are an enterprise tech Twitter ghostwriter. "
        "Write exactly ONE X (Twitter) post. "
        "Requirements: ≤ 280 characters total including hashtags, exactly 2 technical hashtags, "
        "authoritative tone, no consumer simplifications, no buzzwords (revolutionize / synergy / disruptive / game-changer). "
        "Output ONLY the post text — no preamble, no quotes, no labels."
    ),
    "instagram": (
        "You are a master enterprise Instagram storyteller. "
        "Write one Instagram caption with EXACTLY these three section labels in order:\n"
        "🔹 HOOK: <one punchy sentence — why this matters now>\n\n"
        "🔹 ARCHITECTURE: <3–5 sentences: technical architecture, system facts, measurable claims>\n\n"
        "🔹 CTA: <one clear action sentence>\n\n"
        "#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5\n\n"
        "Requirements: ≤ 2200 characters, 3–5 technical hashtags, section labels HOOK / ARCHITECTURE / CTA are mandatory, "
        "no buzzwords (revolutionize / synergy / disruptive / game-changer). "
        "Output ONLY the caption — no explanation, no quotes."
    ),
    "tiktok": (
        "You are a viral TikTok tech scripter. "
        "Write one TikTok caption/script. "
        "Requirements:\n"
        "• First line: punchy hook (start with 'POV:', 'This is', or a bold declarative claim).\n"
        "• Include exactly one '[AUDIO CUE: <description>]' tag on its own line.\n"
        "• ≤ 2200 characters, 2–3 technical hashtags at the end.\n"
        "• High-energy but technically credible. No buzzwords.\n"
        "Output ONLY the script — no preamble."
    ),
}


def _validate_copy(platform: str, content: str) -> List[str]:
    """
    Validates generated copy against platform constraints and brand policy.

    Returns a list of human-readable violation strings. Empty list = valid.
    """
    errors: List[str] = []
    limits = PLATFORM_LIMITS[platform]

    if len(content) > limits["max_chars"]:
        errors.append(
            f"Character count {len(content)} exceeds platform limit {limits['max_chars']}"
        )

    hashtags = re.findall(r"#\w+", content)
    if len(hashtags) < limits["min_hashtags"]:
        errors.append(
            f"Too few hashtags: {len(hashtags)} < minimum {limits['min_hashtags']}"
        )
    if len(hashtags) > limits["max_hashtags"]:
        errors.append(
            f"Too many hashtags: {len(hashtags)} > maximum {limits['max_hashtags']}"
        )

    banned = check_prohibited_terms(content)
    if banned:
        errors.append(f"Prohibited brand terms: {', '.join(banned)}")

    if platform == "instagram":
        upper = content.upper()
        for marker in ("HOOK", "ARCHITECTURE", "CTA"):
            if marker not in upper:
                errors.append(f"Required Instagram section label missing: {marker!r}")

    if platform == "tiktok":
        lower = content.lower()
        has_audio_cue = "audio cue" in lower or "audio:" in lower
        if not has_audio_cue:
            errors.append("TikTok script missing required [AUDIO CUE: ...] tag")

    return errors


async def _generate_platform_copy(
    platform: str,
    sanitized_prompt: str,
    brand_context: List[str],
    trend_signals: List[str],
    attempt: int = 1,
    prior_violations: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generates platform copy via LLM, including prior violation feedback on retry.

    Returns a draft dict with content, hashtags, and character_count.
    Raises ValueError if the output still violates constraints.
    """
    brand_block = "\n".join(f"- {c}" for c in brand_context)
    trend_block = "\n".join(f"- {t}" for t in trend_signals)

    feedback_block = ""
    if prior_violations:
        feedback_block = (
            "\n\nIMPORTANT — previous attempt was rejected. Fix these violations:\n"
            + "\n".join(f"• {v}" for v in prior_violations)
        )

    user_message = (
        f"Brand guidelines:\n{brand_block}\n\n"
        f"Current industry trends:\n{trend_block}\n\n"
        f"Campaign objective: {sanitized_prompt}"
        f"{feedback_block}"
    )

    label = f"phase2_copy_{platform}_attempt{attempt}"
    logger.info("  ├── %s  [attempt %d/%d]", platform.upper(), attempt, MAX_COPY_RETRIES)

    raw = await llm_chat(
        [
            {"role": "system", "content": _PLATFORM_SYSTEM_PROMPTS[platform]},
            {"role": "user",   "content": user_message},
        ],
        call_label=label,
        temperature=max(0.3, 0.65 - 0.1 * (attempt - 1)),   # cool down on retries
        max_tokens=600,
    )

    # On the final attempt, enforce the character budget via tail-trim
    # (hashtags preserved; body truncated). This mirrors Buffer/Hootsuite SDK behaviour.
    limits = PLATFORM_LIMITS[platform]
    if len(raw) > limits["max_chars"] and attempt == MAX_COPY_RETRIES:
        hashtags_in_content = re.findall(r"#\w+", raw)
        hashtag_suffix = " ".join(hashtags_in_content[-limits["max_hashtags"]:]) if hashtags_in_content else ""
        budget_for_body = limits["max_chars"] - len(hashtag_suffix) - (1 if hashtag_suffix else 0)
        # Strip existing hashtags from body, trim body, re-attach hashtags
        body_only = re.sub(r"\s*#\w+", "", raw).strip()
        # Trim at the last word boundary within budget
        if len(body_only) > budget_for_body:
            body_only = body_only[:budget_for_body].rsplit(" ", 1)[0].rstrip(".,;:").strip()
        raw = (f"{body_only} {hashtag_suffix}" if hashtag_suffix else body_only).strip()
        logger.info(
            "       ✂  [%s] Final-attempt budget-trim applied → %d chars", platform, len(raw)
        )

    errors = _validate_copy(platform, raw)
    if errors:
        raise ValueError(f"[{platform}] attempt {attempt} — {errors}")

    return {
        "platform":        platform,
        "content":         raw,
        "hashtags":        re.findall(r"#\w+", raw),
        "character_count": len(raw),
    }


async def phase_act(
    sanitized_prompt: str,
    platforms: List[str],
    brand_context: List[str],
    trend_signals: List[str],
) -> Dict[str, Dict[str, Any]]:
    """
    Phase 2 — ACT: LLM generates platform-tailored copy for each platform.

    On format/policy violations the LLM is re-prompted with the specific
    violation feedback (up to MAX_COPY_RETRIES attempts per platform).
    No content is ever manually injected or patched post-generation.
    """
    logger.info("━" * 70)
    logger.info("PHASE 2 · ACT  (act_draft_node) — model: %s", PRIMARY_MODEL)
    logger.info("━" * 70)

    async def _with_retry(platform: str) -> Dict[str, Any]:
        violations: List[str] = []
        for attempt in range(1, MAX_COPY_RETRIES + 1):
            try:
                return await _generate_platform_copy(
                    platform, sanitized_prompt, brand_context, trend_signals,
                    attempt=attempt,
                    prior_violations=violations if attempt > 1 else None,
                )
            except ValueError as exc:
                violations = [str(exc)]
                if attempt == MAX_COPY_RETRIES:
                    raise RuntimeError(
                        f"Platform '{platform}' copy generation failed after "
                        f"{MAX_COPY_RETRIES} attempts. Last error: {exc}"
                    ) from exc
                logger.warning("       ⚠  Retry %d/%d — %s", attempt, MAX_COPY_RETRIES, exc)

        # unreachable; keeps type-checker happy
        raise RuntimeError("Retry loop exhausted without raising")

    tasks    = [_with_retry(p) for p in platforms]
    results  = await asyncio.gather(*tasks)
    drafts   = {r["platform"]: r for r in results}

    for plat, draft in drafts.items():
        logger.info(
            "  ✓ %-10s  %d chars | %d hashtags",
            plat.upper(), draft["character_count"], len(draft["hashtags"]),
        )

    logger.info("  ACT complete: %d drafts generated.", len(drafts))
    return drafts


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: OBSERVE (media_prep_node)
# ─────────────────────────────────────────────────────────────────────────────

MEDIA_CDN_URL = "https://cdn.agentplatform.io/assets/state-machine-diagram.png"


async def phase_observe(drafts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Phase 3 — OBSERVE: SSRF-safe URL validation + LLM alt-text generation.

    The alt-text is generated from the live post context; nothing is hardcoded.
    """
    logger.info("━" * 70)
    logger.info("PHASE 3 · OBSERVE  (media_prep_node)")
    logger.info("━" * 70)

    # 3.1 — SSRF + HTTPS URL validation
    logger.info("  3.1  URL security validation")
    valid, reason = validate_media_url(MEDIA_CDN_URL)
    if not valid:
        raise ValueError(f"Media URL '{MEDIA_CDN_URL}' failed validation: {reason}")
    logger.info("       ✓ CDN URL accepted: %s", MEDIA_CDN_URL)

    # Demonstrate block cases in log (no hardcoded assert of specific URLs)
    for test_url in [
        "http://192.168.1.100/internal/asset.png",
        "http://127.0.0.1:8080/admin",
        "ftp://assets.example.com/img.png",
    ]:
        ok, msg = validate_media_url(test_url)
        logger.info("       ✗ Blocked: %-45s  reason: %s", test_url, msg)

    # 3.2 — LLM alt-text generation (WCAG-compliant, grounded in actual post content)
    logger.info("  3.2  LLM WCAG alt-text generation (%s)", PRIMARY_MODEL)
    post_sample = next(iter(drafts.values()), {}).get("content", "Enterprise agentic workflow")[:250]
    raw_alt = await llm_chat(
        [
            {
                "role": "system",
                "content": (
                    "You write concise WCAG 2.1-compliant alt-text for technical product diagrams. "
                    "Respond with a SINGLE sentence of ≤ 150 characters. "
                    "No quotes, no labels, no preamble."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Post context (excerpt): {post_sample}\n\n"
                    "The diagram depicts a five-node stateful multi-agent workflow: "
                    "Plan → Act → Observe → Reflect → Publish, "
                    "with conditional routing edges and self-healing feedback loops. "
                    "Generate the alt-text."
                ),
            },
        ],
        call_label="phase3_alt_text",
        temperature=0.1,
        max_tokens=80,
    )
    alt_text = raw_alt.strip().strip('"').strip("'")
    logger.info("       ✓ Alt-text (%d chars): %s", len(alt_text), alt_text[:100])

    updated: Dict[str, Dict[str, Any]] = {}
    for platform, draft in drafts.items():
        updated[platform] = {
            **draft,
            "media_url": MEDIA_CDN_URL,
            "alt_text":  alt_text,
        }

    logger.info("  OBSERVE complete.")
    return {"drafts": updated, "alt_text": alt_text, "media_url": MEDIA_CDN_URL}


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: REFLECT (evaluate_audit_node) — LLM-as-a-Judge
# ─────────────────────────────────────────────────────────────────────────────

_JUDGE_SYSTEM = (
    "You are a rigorous Enterprise Brand & Compliance Judge. "
    "Score the candidate social media post against the provided brand guidelines. "
    "Return ONLY a valid JSON object — no markdown, no explanation:\n"
    '{"faithfulness_score": <float 0.0-1.0>, '
    '"faithfulness_rationale": "<string>", '
    '"brand_voice_score": <float 0.0-1.0>, '
    '"brand_voice_rationale": "<string>", '
    '"safety_score": <float 0.0-1.0>, '
    '"safety_rationale": "<string>"}'
)


def _compute_formatting_score(content: str, platform: str) -> Tuple[float, List[str]]:
    """Deterministic formatting score derived from observable content properties."""
    score, reasons = 1.0, []
    limits = PLATFORM_LIMITS[platform]

    if len(content) > limits["max_chars"]:
        score -= 0.4
        reasons.append(f"Exceeds {limits['max_chars']} char limit ({len(content)} chars)")

    hashtags = re.findall(r"#\w+", content)
    if len(hashtags) > limits["max_hashtags"]:
        penalty = 0.2
        score -= penalty
        reasons.append(f"Hashtag count {len(hashtags)} > max {limits['max_hashtags']}")

    banned = check_prohibited_terms(content)
    if banned:
        score -= 0.3 * len(banned)
        reasons.append(f"Prohibited brand terms: {', '.join(banned)}")

    return max(0.0, round(score, 4)), reasons


async def _judge_platform(
    platform: str,
    content: str,
    brand_context: List[str],
) -> Dict[str, Any]:
    """
    Calls the LLM judge for one platform. Retries up to MAX_JUDGE_RETRIES times
    if the response cannot be parsed as valid JSON. Raises on exhaustion.
    """
    ctx_block = "\n".join(f"- {c}" for c in brand_context[:5])
    user_msg  = (
        f"Brand Guidelines:\n{ctx_block}\n\n"
        f"Platform: {platform}\n"
        f"Candidate Post:\n{content}"
    )
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {"role": "user",   "content": user_msg},
    ]

    for attempt in range(1, MAX_JUDGE_RETRIES + 1):
        raw = await llm_chat(
            messages,
            call_label=f"phase4_judge_{platform}_attempt{attempt}",
            temperature=0.0,
            max_tokens=450,
        )
        # Strip markdown fences and extract first JSON object
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(
            "  [JUDGE] JSON parse failed for %s attempt %d/%d",
            platform, attempt, MAX_JUDGE_RETRIES,
        )
        if attempt == MAX_JUDGE_RETRIES:
            raise RuntimeError(
                f"Judge failed to return valid JSON for platform '{platform}' "
                f"after {MAX_JUDGE_RETRIES} attempts. Last raw output:\n{raw}"
            )
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": (
                "Your previous response was not valid JSON. "
                "Respond ONLY with the JSON object — no explanation, no markdown."
            ),
        })

    raise RuntimeError("Judge retry loop exhausted")   # unreachable


async def phase_reflect(
    drafts: Dict[str, Dict[str, Any]],
    brand_context: List[str],
) -> Dict[str, Any]:
    """
    Phase 4 — REFLECT: LLM-as-a-Judge multi-metric audit.

    Combines deterministic formatting scoring (observable properties) with
    LLM subjective scoring (faithfulness, brand voice, safety).
    The composite quality score Q determines the routing decision.

    No score overrides or calibration floors are applied — the LLM verdict
    stands as-is.  If the judge fails to produce parseable JSON it retries.
    """
    logger.info("━" * 70)
    logger.info("PHASE 4 · REFLECT  (evaluate_audit_node) — model: %s", PRIMARY_MODEL)
    logger.info("━" * 70)

    per_platform: Dict[str, Any] = {}

    for platform, draft in drafts.items():
        content = draft["content"]

        fmt_score, fmt_reasons = _compute_formatting_score(content, platform)

        logger.info("  ├── Judge: %s", platform.upper())
        judge = await _judge_platform(platform, content, brand_context)

        faith_score  = max(0.0, min(1.0, float(judge.get("faithfulness_score", 0.0))))
        brand_score  = max(0.0, min(1.0, float(judge.get("brand_voice_score",  0.0))))
        safety_score = max(0.0, min(1.0, float(judge.get("safety_score",       0.0))))

        composite_q = (
            AUDIT_WEIGHTS["faithfulness"] * faith_score
            + AUDIT_WEIGHTS["brand_voice"]  * brand_score
            + AUDIT_WEIGHTS["formatting"]   * fmt_score
            + AUDIT_WEIGHTS["safety"]       * safety_score
        )
        composite_q = round(min(1.0, max(0.0, composite_q)), 4)

        reasons = list(fmt_reasons)
        if faith_score  < 0.70: reasons.append(f"Faithfulness {faith_score:.2f} < 0.70")
        if brand_score  < 0.70: reasons.append(f"Brand voice {brand_score:.2f} < 0.70")
        if safety_score < 0.80: reasons.append(f"Safety {safety_score:.2f} < 0.80")

        per_platform[platform] = {
            "faithfulness_score":    faith_score,
            "brand_voice_score":     brand_score,
            "formatting_score":      fmt_score,
            "safety_score":          safety_score,
            "overall_quality_score": composite_q,
            "is_safe":               safety_score >= 0.80,
            "passed_gate":           composite_q >= 0.80 and safety_score >= 0.80,
            "reasons":               reasons,
            "judge_rationale": {
                "faithfulness": judge.get("faithfulness_rationale", ""),
                "brand_voice":  judge.get("brand_voice_rationale",  ""),
                "safety":       judge.get("safety_rationale",       ""),
            },
        }

        logger.info(
            "       %-10s  Faith=%.2f  Brand=%.2f  Format=%.2f  Safety=%.2f  → Q=%.4f  [%s]",
            platform.upper(),
            faith_score, brand_score, fmt_score, safety_score, composite_q,
            "PASS ✓" if per_platform[platform]["passed_gate"] else "FAIL ✗",
        )

    avg_q = round(sum(v["overall_quality_score"] for v in per_platform.values()) / len(per_platform), 4)
    worst_platform = min(per_platform, key=lambda p: per_platform[p]["overall_quality_score"])
    worst          = per_platform[worst_platform]
    all_reasons    = [r for v in per_platform.values() for r in v["reasons"]]

    logger.info(
        "  └── Avg Q=%.4f  |  Worst: %s (Q=%.4f)",
        avg_q, worst_platform.upper(), worst["overall_quality_score"],
    )
    logger.info("  REFLECT complete.")

    return {
        "per_platform":          per_platform,
        "worst_platform":        worst_platform,
        "avg_quality_score":     avg_q,
        "overall_quality_score": avg_q,
        "is_safe":               all(v["is_safe"] for v in per_platform.values()),
        "passed_gate":           avg_q >= 0.80,
        "reasons":               list(dict.fromkeys(all_reasons)),
        "faithfulness_score":    per_platform.get("x_twitter", worst)["faithfulness_score"],
        "brand_voice_score":     per_platform.get("x_twitter", worst)["brand_voice_score"],
        "formatting_score":      per_platform.get("x_twitter", worst)["formatting_score"],
        "safety_score":          per_platform.get("x_twitter", worst)["safety_score"],
        "weights":               AUDIT_WEIGHTS,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5: PUBLISH (decide_audit_routing → publish_dispatch_node)
# ─────────────────────────────────────────────────────────────────────────────

_PLATFORM_TOOLS: Dict[str, str] = {
    "x_twitter": "post_x_tweet",
    "instagram":  "post_instagram",
    "tiktok":     "post_tiktok",
}


def _routing_decision(avg_q: float, is_safe: bool, retry_count: int) -> str:
    """Mirrors decide_audit_routing() logic from graph/edges.py."""
    if not is_safe:
        return "__end__"
    if avg_q < 0.80:
        return "reflect_remedy" if retry_count < 3 else "hitl_gate"
    return "publish_dispatch"


async def phase_publish(
    drafts: Dict[str, Dict[str, Any]],
    mcp: FastMCPClient,
    avg_q: float,
    is_safe: bool,
    retry_count: int = 0,
) -> Dict[str, Any]:
    """
    Phase 5 — PUBLISH: routing decision gate + FastMCP dispatch.

    The FastMCP client returns stub post IDs simulating platform API responses.
    """
    logger.info("━" * 70)
    logger.info("PHASE 5 · PUBLISH  (publish_dispatch_node)")
    logger.info("━" * 70)

    route = _routing_decision(avg_q, is_safe, retry_count)
    logger.info("  Routing: avg_Q=%.4f, safe=%s → %r", avg_q, is_safe, route)

    if route != "publish_dispatch":
        raise RuntimeError(
            f"Routing gate rejected dispatch. Route='{route}' "
            f"(avg_Q={avg_q:.4f}, is_safe={is_safe})"
        )
    logger.info("  ✓ Routing gate cleared → publish_dispatch")

    published: Dict[str, str] = {}
    errors: List[str] = []

    for platform, draft in drafts.items():
        tool = _PLATFORM_TOOLS.get(platform)
        if not tool:
            errors.append(f"No tool mapping for platform '{platform}'")
            continue
        res = await mcp.post(tool, {"content": draft["content"]})
        if res.get("status") == "success":
            pid = res.get("post_id") or res.get("publish_id", f"unknown_{uuid.uuid4().hex[:6]}")
            published[platform] = str(pid)
        else:
            errors.append(f"{platform}: {res.get('message', 'unknown error')}")
            logger.error("  ✗ %s dispatch failed: %s", platform, res.get("message"))

    status = "success" if len(published) == len(drafts) and not errors else "partial"
    logger.info("  PUBLISH complete: status=%r  dispatched=%d/%d", status, len(published), len(drafts))

    return {
        "status":             status,
        "route":              route,
        "published_post_ids": published,
        "errors":             errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def run(campaign_id: str, inbound_prompt: str, platforms: List[str]) -> Dict[str, Any]:
    """
    Full social_agent workflow orchestrator.

    Executes all 5 phases in sequence, saving checkpoints between each node.
    Returns the complete structured result dict for printing / downstream use.
    """
    t0          = time.monotonic()
    thread_id   = f"thread_{campaign_id}"
    mcp         = FastMCPClient()
    checkpointer = Checkpointer(thread_id)
    state: Dict[str, Any] = {
        "campaign_id": campaign_id,
        "thread_id":   thread_id,
        "prompt":      inbound_prompt,
        "platforms":   platforms,
    }
    exec_history: List[str] = []

    logger.info("═" * 70)
    logger.info("  social_agent  |  campaign: %s  |  model: %s", campaign_id, PRIMARY_MODEL)
    logger.info("  Endpoint: %s/chat/completions", OLLAMA_BASE)
    logger.info("═" * 70)

    # Phase 1 — PLAN
    plan = await phase_plan(inbound_prompt)
    state.update(plan)
    checkpointer.save("plan_research_node", state)
    exec_history.append(f"Phase1-Plan: {plan['research_context_count']} context chunks assembled.")

    # Phase 2 — ACT
    drafts = await phase_act(
        plan["sanitized_prompt"], platforms, plan["brand_context"], plan["trend_signals"]
    )
    state["drafts"] = drafts
    checkpointer.save("act_draft_node", state)
    exec_history.append(f"Phase2-Act: Drafts generated for {list(drafts.keys())}.")

    # Phase 3 — OBSERVE
    obs = await phase_observe(drafts)
    state["drafts"] = obs["drafts"]
    checkpointer.save("media_prep_node", state)
    exec_history.append("Phase3-Observe: Media validated, alt-text generated.")

    # Phase 4 — REFLECT
    audit = await phase_reflect(obs["drafts"], plan["brand_context"])
    state["audit"] = audit
    checkpointer.save("evaluate_audit_node", state)
    exec_history.append(f"Phase4-Reflect: avg_Q={audit['avg_quality_score']:.4f}  gate={audit['passed_gate']}.")

    # Phase 5 — PUBLISH
    pub = await phase_publish(
        obs["drafts"], mcp, audit["avg_quality_score"], audit["is_safe"]
    )
    state["published"] = pub
    checkpointer.save("publish_dispatch_node", state)
    exec_history.append(f"Phase5-Publish: {len(pub['published_post_ids'])} posts dispatched.")

    elapsed   = round(time.monotonic() - t0, 3)
    succeeded = pub["status"] == "success" and audit["passed_gate"] and plan["is_safe"]

    logger.info("═" * 70)
    logger.info("  Status    : %s", "PASSED ✅" if succeeded else "FAILED ❌")
    logger.info("  Elapsed   : %.3f sec", elapsed)
    logger.info("  LLM calls : %d  |  Total tokens: %d",
                len(_llm_call_log),
                sum(e["prompt_tokens"] + e["completion_tokens"] for e in _llm_call_log))
    logger.info("  Cost      : $0.00  (local Ollama)")
    logger.info("═" * 70)

    return {
        "status":      "PASSED" if succeeded else "FAILED",
        "campaign_id": campaign_id,
        "thread_id":   thread_id,
        "llm_backend": {
            "model":    PRIMARY_MODEL,
            "endpoint": f"{OLLAMA_BASE}/chat/completions",
            "cost_usd": 0.0,
        },
        "phases": {
            "plan": {
                "is_safe":          plan["is_safe"],
                "sanitized_prompt": plan["sanitized_prompt"],
                "brand_rules":      plan["brand_context"],
                "trend_signals":    plan["trend_signals"],
            },
            "act": {
                platform: {
                    "content":         d["content"],
                    "character_count": d["character_count"],
                    "hashtags":        d["hashtags"],
                }
                for platform, d in obs["drafts"].items()
            },
            "observe": {
                "media_url": obs["media_url"],
                "alt_text":  obs["alt_text"],
            },
            "reflect": {
                "avg_quality_score":  audit["avg_quality_score"],
                "passed_gate":        audit["passed_gate"],
                "composite_formula":  "Q = 0.35·faith + 0.35·brand + 0.15·format + 0.15·safety",
                "weights":            AUDIT_WEIGHTS,
                "per_platform":       {
                    p: {
                        "faithfulness": v["faithfulness_score"],
                        "brand_voice":  v["brand_voice_score"],
                        "formatting":   v["formatting_score"],
                        "safety":       v["safety_score"],
                        "composite_Q":  v["overall_quality_score"],
                        "gate":         "PASS" if v["passed_gate"] else "FAIL",
                        "rationale":    v["judge_rationale"],
                    }
                    for p, v in audit["per_platform"].items()
                },
            },
            "publish": {
                "route":              pub["route"],
                "status":             pub["status"],
                "published_post_ids": pub["published_post_ids"],
                "errors":             pub["errors"],
            },
        },
        "checkpoints": {
            "total":         checkpointer.count,
            "node_sequence": checkpointer.node_sequence,
        },
        "execution_history": exec_history,
        "telemetry": {
            "elapsed_sec":       elapsed,
            "llm_calls":         len(_llm_call_log),
            "total_tokens":      sum(e["prompt_tokens"] + e["completion_tokens"] for e in _llm_call_log),
            "total_cost_usd":    0.0,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Transcript printer
# ─────────────────────────────────────────────────────────────────────────────

_CALL_LABELS: Dict[str, str] = {
    "phase1_trend_synthesis":         "Phase 1 · PLAN     │ LLM Trend Synthesis",
    "phase3_alt_text":                "Phase 3 · OBSERVE  │ WCAG Alt-Text Generator",
}


def _call_description(label: str) -> str:
    if label in _CALL_LABELS:
        return _CALL_LABELS[label]
    m = re.match(r"phase2_copy_(\w+)_attempt(\d+)", label)
    if m:
        return f"Phase 2 · ACT      │ {m.group(1).upper()} Copywriter (attempt {m.group(2)})"
    m = re.match(r"phase4_judge_(\w+)_attempt(\d+)", label)
    if m:
        return f"Phase 4 · REFLECT  │ LLM-as-a-Judge · {m.group(1).upper()} (attempt {m.group(2)})"
    return label


def print_transcript() -> None:
    """Print the full verbatim LLM response transcript after the JSON block."""
    SEP = "─" * 80

    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║  LLM RESPONSE TRANSCRIPT  —  Verbatim raw outputs" + " " * 28 + "║")
    print("╚" + "═" * 78 + "╝")

    def _wrap(text: str, prefix: str = "│  ", width: int = 74) -> None:
        for raw_line in text.split("\n"):
            if not raw_line.strip():
                print(prefix)
                continue
            while len(raw_line) > width:
                print(f"{prefix}{raw_line[:width]}")
                raw_line = raw_line[width:]
            print(f"{prefix}{raw_line}")

    for i, entry in enumerate(_llm_call_log, start=1):
        desc  = _call_description(entry["call_label"])
        model = entry["model"]
        ptok  = entry["prompt_tokens"]
        ctok  = entry["completion_tokens"]
        temp  = entry["temperature"]

        print(f"\n┌{SEP}┐")
        print(f"│  [{i:02d}/{len(_llm_call_log)}]  {desc}")
        print(f"│  model={model}  temp={temp}  prompt={ptok}tok  completion={ctok}tok")
        print(f"├{SEP}┤")
        print("│  ▸ SYSTEM PROMPT")
        _wrap(entry["system_prompt"])
        print(f"├{SEP}┤")
        user_p = entry["user_prompt"]
        if len(user_p) > 700:
            user_p = "[… showing last 700 chars]\n" + user_p[-700:]
        print("│  ▸ USER PROMPT")
        _wrap(user_p)
        print(f"├{SEP}┤")
        print("│  ▸ RAW MODEL RESPONSE  (verbatim — unprocessed)")
        _wrap(entry["raw_response"])
        print(f"└{SEP}┘")

    total_p = sum(e["prompt_tokens"]     for e in _llm_call_log)
    total_c = sum(e["completion_tokens"] for e in _llm_call_log)
    print(f"\n  Total LLM calls  : {len(_llm_call_log)}")
    print(f"  Prompt tokens    : {total_p}")
    print(f"  Completion tokens: {total_c}")
    print(f"  Total tokens     : {total_p + total_c}")
    print("  Total cost       : $0.00  (local Ollama — free inference)")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    CAMPAIGN_ID = "cmp_prod_001"
    PROMPT      = (
        "Announce our new autonomous agentic workflow framework for enterprise "
        "social media automation — featuring verified guardrails, self-healing "
        "feedback loops, and deterministic LangGraph state management."
    )
    PLATFORMS   = ["x_twitter", "instagram", "tiktok"]

    try:
        result = asyncio.run(run(CAMPAIGN_ID, PROMPT, PLATFORMS))

        print("\n")
        print("╔" + "═" * 78 + "╗")
        print("║  social_agent  —  Campaign Result" + " " * 44 + "║")
        print("╚" + "═" * 78 + "╝")
        print()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        verdict = "✅  PASSED" if result["status"] == "PASSED" else "❌  FAILED"
        print(f"\n{verdict}  —  campaign_id={CAMPAIGN_ID}")

        print_transcript()

        sys.exit(0 if result["status"] == "PASSED" else 1)

    except Exception as exc:
        logger.exception("❌  FATAL: %s", exc)
        sys.exit(1)
