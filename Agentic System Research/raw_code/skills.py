# File: skills.py
"""
Production-grade Skills Subsystem for Governed Agentic AI Architectures.

Architecture & Invariants:
1. Guidance != Authority: A Skill provides procedural tradecraft (how, when, sequence).
   It CANNOT grant tools, elevate permissions, expand tenant/data scopes, override budgets,
   or bypass HITL gates.
   Path: Skill Guidance -> Policy Boundary -> Authorized Tool Execution.
2. Self-Contained Skill Package: Manifest, Operational Guidance (SKILL.md),
   Deterministic Assets, and Domain References with cryptographic provenance hashing.
3. Progressive Disclosure:
   - Discovery: Exposes lightweight metadata (name, description, category, suggested tools).
   - Execution: Loads full procedural guidance into invocation context on demand upon authorization.
   - Eviction: Cleanses loaded instructions from working memory post-task.
4. Hierarchical Attenuation:
   Publisher -> Orchestrator (Registry Owner) -> Worker (Domain Scope) -> Sub-Agent (Narrow Atomic Slice).
"""

from __future__ import annotations

import copy
import dataclasses
import enum
import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("skills")


# ============================================================================
# 1. ENUMS AND DATA CONTRACTS
# ============================================================================

class SkillCategory(str, enum.Enum):
    MARKETING = "marketing"
    COMPLIANCE = "compliance"
    CREATIVE = "creative"
    DEVELOPMENT = "development"
    ANALYTICS = "analytics"
    OPERATIONS = "operations"


class ActionRiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclasses.dataclass(frozen=True)
class SkillMetadata:
    """Lightweight metadata exposed during discovery to minimize context bloat."""
    skill_id: str
    name: str
    version: str
    description: str
    category: SkillCategory
    target_domains: Tuple[str, ...]
    suggested_tools: Tuple[str, ...]
    publisher_id: str
    package_hash: str


@dataclasses.dataclass(frozen=True)
class DeterministicAsset:
    """Executable helper script, linter, or code template run in isolated sandboxes."""
    asset_id: str
    name: str
    asset_type: str
    code_payload: str
    entrypoint: str
    content_hash: str


@dataclasses.dataclass(frozen=True)
class DomainReference:
    """Static schema, dictionary, or compliance specification."""
    reference_id: str
    name: str
    uri: str
    mime_type: str
    content: str
    content_hash: str


@dataclasses.dataclass(frozen=True)
class OperationalGuidance:
    """Full procedural instructions (SKILL.md equivalent)."""
    guidance_id: str
    skill_id: str
    instructions_markdown: str
    checklists: Tuple[str, ...]
    evaluation_criteria: Tuple[str, ...]
    formatting_rules: Dict[str, str]
    content_hash: str


@dataclasses.dataclass(frozen=True)
class SkillManifest:
    """Authoritative manifest specifying identity, contracts, and provenance."""
    skill_id: str
    name: str
    version: str
    description: str
    category: SkillCategory
    publisher_id: str
    target_domains: Tuple[str, ...]
    suggested_tools: Tuple[str, ...]
    required_inputs: Dict[str, str]
    expected_outputs: Dict[str, str]
    created_at: datetime
    package_hash: str


@dataclasses.dataclass
class SkillPackage:
    """Self-contained, versioned, cryptographic package of tradecraft."""
    manifest: SkillManifest
    guidance: OperationalGuidance
    assets: Dict[str, DeterministicAsset] = dataclasses.field(default_factory=dict)
    references: Dict[str, DomainReference] = dataclasses.field(default_factory=dict)

    def verify_integrity(self) -> bool:
        """Verifies package integrity against manifest hash."""
        computed = self.compute_package_hash(self.manifest.skill_id, self.guidance, self.assets, self.references)
        return computed == self.manifest.package_hash

    @staticmethod
    def compute_package_hash(skill_id: str, guidance: OperationalGuidance,
                             assets: Dict[str, DeterministicAsset],
                             references: Dict[str, DomainReference]) -> str:
        h = hashlib.sha256()
        h.update(f"skill:{skill_id}::".encode("utf-8"))
        h.update(guidance.content_hash.encode("utf-8"))
        for k in sorted(assets.keys()):
            h.update(f"::asset:{k}:{assets[k].content_hash}".encode("utf-8"))
        for k in sorted(references.keys()):
            h.update(f"::ref:{k}:{references[k].content_hash}".encode("utf-8"))
        return h.hexdigest()


# ============================================================================
# 2. PROGRESSIVE DISCLOSURE & RUNTIME CONTEXT
# ============================================================================

@dataclasses.dataclass
class LoadedSkillContext:
    """
    Temporary staged skill context loaded for execution.
    Contains instructions and references, but NEVER tool permissions or scopes.
    """
    skill_id: str
    session_id: str
    agent_id: str
    tenant_id: str
    instructions_text: str
    checklists: List[str]
    available_references: Dict[str, str]
    suggested_tools: Set[str]
    is_active: bool = True
    loaded_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))

    def render_prompt_injection(self) -> str:
        """Renders procedural guidance cleanly for prompt insertion."""
        if not self.is_active:
            raise RuntimeError("Cannot render instructions from evicted SkillContext.")
        lines = [
            f"=== SKILL PLAYBOOK: {self.skill_id} ===",
            "NOTE: This playbook provides guidance only. Tool execution is independently authorized by the system.",
            "--- PROCEDURAL INSTRUCTIONS ---",
            self.instructions_text,
            "--- MANDATORY CHECKLIST ---"
        ]
        for c in self.checklists:
            lines.append(f"[ ] {c}")
        return chr(10).join(lines)

    def evict(self) -> None:
        """Evicts full instructions from working context upon turn/task completion."""
        self.is_active = False
        self.instructions_text = ""
        self.checklists.clear()
        self.available_references.clear()
        logger.debug("SkillContext for %s evicted from agent %s.", self.skill_id, self.agent_id)


# ============================================================================
# 3. GOVERNED POLICY INTERCEPTION & MONOTONIC CAPABILITY ENFORCER
# ============================================================================

@dataclasses.dataclass(frozen=True)
class ActionProposal:
    """Candidate tool action proposed by an agent following Skill guidance."""
    proposal_id: str
    proposing_agent_id: str
    skill_id: str
    tool_name: str
    tool_arguments: Dict[str, Any]
    action_risk: ActionRiskLevel
    justification: str
    timestamp: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))


@dataclasses.dataclass(frozen=True)
class PolicyAuthorizationDecision:
    """Decision emitted by the policy boundary before any execution occurs."""
    is_authorized: bool
    proposal_id: str
    effective_tool_name: str
    reason: str
    cleared_at: Optional[datetime] = None
    clearance_token: Optional[str] = None


class SkillPolicyEnforcer:
    """
    Enforces that Skills cannot grant permissions or bypass orchestrator policy.
    Formula: Effective Route = Host Policy ∩ Worker Grant ∩ Sub-Agent Scope ∩ Server Auth.
    """

    @staticmethod
    def evaluate_proposal(proposal: ActionProposal,
                          tenant_id: str,
                          host_policy_allowlist: Set[str],
                          worker_task_grant_tools: Set[str],
                          subagent_permitted_tools: Set[str],
                          server_authorized_tools: Set[str]) -> PolicyAuthorizationDecision:
        tool = proposal.tool_name

        # 1. Monotonic Capability Intersection
        effective_capabilities = (
            host_policy_allowlist
            .intersection(worker_task_grant_tools)
            .intersection(subagent_permitted_tools)
            .intersection(server_authorized_tools)
        )

        # 2. Strict Verification
        if tool not in effective_capabilities:
            reason = (
                f"Policy Violation: Tool '{tool}' proposed via skill '{proposal.skill_id}' "
                f"is not in the effective capability allowlist {list(effective_capabilities)}. "
                "Skill guidance cannot grant tools or escalate privileges."
            )
            logger.warning(reason)
            return PolicyAuthorizationDecision(
                is_authorized=False,
                proposal_id=proposal.proposal_id,
                effective_tool_name=tool,
                reason=reason
            )

        # 3. Issue Short-Lived Execution Clearance
        token = f"CLR_{uuid.uuid4().hex[:12]}"
        logger.info("Tool '%s' proposed by agent '%s' (Skill '%s') AUTHORIZED.",
                    tool, proposal.proposing_agent_id, proposal.skill_id)
        return PolicyAuthorizationDecision(
            is_authorized=True,
            proposal_id=proposal.proposal_id,
            effective_tool_name=tool,
            reason="Authorized: Passed monotonic capability intersection checks.",
            cleared_at=datetime.now(timezone.utc),
            clearance_token=token
        )


# ============================================================================
# 4. HIERARCHICAL SLICING (WORKER VS SUB-AGENT)
# ============================================================================

class HierarchicalSkillSlicer:
    """
    Attenuates skill instructions down the hierarchy:
    Worker receives full domain guidance; Sub-Agent receives only narrow atomic slices.
    """

    @staticmethod
    def create_subagent_slice(parent_context: LoadedSkillContext, subagent_id: str,
                              target_subtask: str, permitted_tools_slice: Set[str]) -> LoadedSkillContext:
        if not parent_context.is_active:
            raise RuntimeError("Cannot slice an inactive or evicted parent SkillContext.")

        # Filter checklists matching subtask keyword
        sub_checklists = [c for c in parent_context.checklists if any(k in c.lower() for k in target_subtask.lower().split())]
        if not sub_checklists:
            sub_checklists = parent_context.checklists[:1]  # At most 1 checklist item for micro-task

        # Attenuate suggested tools strictly to subagent's allowed slice
        effective_tools = parent_context.suggested_tools.intersection(permitted_tools_slice)

        slice_text = f"MICRO-TASK SCOPE: {target_subtask}\nFocus exclusively on this atomic requirement. Adhere to parent constraints."

        return LoadedSkillContext(
            skill_id=parent_context.skill_id,
            session_id=parent_context.session_id,
            agent_id=subagent_id,
            tenant_id=parent_context.tenant_id,
            instructions_text=slice_text,
            checklists=sub_checklists,
            available_references=dict(parent_context.available_references),
            suggested_tools=effective_tools,
            is_active=True
        )


# ============================================================================
# 5. DETERMINISTIC ASSET SANDBOX RUNNER
# ============================================================================

class DeterministicAssetSandbox:
    """Executes deterministic helper assets (code templates, linters) in bounded environments."""

    @staticmethod
    def execute_regex_linter(asset: DeterministicAsset, text_to_lint: str, pattern: str) -> Dict[str, Any]:
        """Runs deterministic regex validation against provided content."""
        if asset.asset_type != "regex_linter":
            raise ValueError(f"Incompatible asset type: {asset.asset_type}")
        
        matches = list(re.finditer(pattern, text_to_lint, re.IGNORECASE))
        violations = [m.group(0) for m in matches]
        return {
            "asset_id": asset.asset_id,
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations
        }


# ============================================================================
# 6. CENTRAL ORCHESTRATOR SKILL REGISTRY
# ============================================================================

class SkillRegistry:
    """
    Central Orchestrator-owned repository for published Skill Packages.
    Manages registration, discovery-time filtering, progressive disclosure staging,
    and post-task eviction.
    """

    def __init__(self):
        self._packages: Dict[str, SkillPackage] = {}
        self._active_contexts: Dict[str, LoadedSkillContext] = {}
        self._audit_log: List[Dict[str, Any]] = []

    def _log_audit(self, event_type: str, details: Dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details
        }
        self._audit_log.append(entry)
        logger.debug("Skill audit: %s | %s", event_type, details)

    def publish_package(self, package: SkillPackage) -> str:
        """Registers and validates the cryptographic integrity of a Skill Package."""
        if not package.verify_integrity():
            raise ValueError(f"Package {package.manifest.skill_id} failed cryptographic hash verification.")
        
        skill_id = package.manifest.skill_id
        self._packages[skill_id] = package
        self._log_audit("SKILL_PUBLISHED", {
            "skill_id": skill_id,
            "version": package.manifest.version,
            "publisher": package.manifest.publisher_id,
            "hash": package.manifest.package_hash
        })
        logger.info("Skill '%s' (v%s) published by '%s' with hash %s",
                    package.manifest.name, package.manifest.version,
                    package.manifest.publisher_id, package.manifest.package_hash[:8])
        return skill_id

    def discover_skills(self, tenant_id: str, caller_domain: str,
                        permitted_domains: Set[str]) -> List[SkillMetadata]:
        """
        Discovery-Time Filtering: Exposes only lightweight metadata for allowed domains.
        Full operational instructions are NOT loaded into context here.
        """
        results: List[SkillMetadata] = []
        for pkg in self._packages.values():
            if not set(pkg.manifest.target_domains).intersection(permitted_domains):
                continue
            
            meta = SkillMetadata(
                skill_id=pkg.manifest.skill_id,
                name=pkg.manifest.name,
                version=pkg.manifest.version,
                description=pkg.manifest.description,
                category=pkg.manifest.category,
                target_domains=pkg.manifest.target_domains,
                suggested_tools=pkg.manifest.suggested_tools,
                publisher_id=pkg.manifest.publisher_id,
                package_hash=pkg.manifest.package_hash
            )
            results.append(meta)

        self._log_audit("SKILLS_DISCOVERED", {
            "tenant_id": tenant_id,
            "caller_domain": caller_domain,
            "count": len(results)
        })
        return results

    def load_skill_for_execution(self, skill_id: str, session_id: str,
                                 agent_id: str, tenant_id: str,
                                 agent_task_grant_domains: Set[str]) -> LoadedSkillContext:
        """
        Execution-Time Staging: Loads full operational guidance only upon explicit authorization.
        Enforces tenant and domain verification before loading into working context.
        """
        if skill_id not in self._packages:
            raise KeyError(f"Skill '{skill_id}' does not exist in registry.")

        pkg = self._packages[skill_id]

        if not set(pkg.manifest.target_domains).intersection(agent_task_grant_domains):
            raise PermissionError(f"Agent '{agent_id}' does not have domain clearance for skill '{skill_id}'.")

        context_key = f"{session_id}::{agent_id}::{skill_id}"
        ctx = LoadedSkillContext(
            skill_id=skill_id,
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            instructions_text=pkg.guidance.instructions_markdown,
            checklists=list(pkg.guidance.checklists),
            available_references={k: ref.content for k, ref in pkg.references.items()},
            suggested_tools=set(pkg.manifest.suggested_tools),
            is_active=True
        )
        self._active_contexts[context_key] = ctx

        self._log_audit("SKILL_LOADED_FOR_EXECUTION", {
            "skill_id": skill_id,
            "session_id": session_id,
            "agent_id": agent_id,
            "tenant_id": tenant_id
        })
        logger.info("Skill '%s' loaded into execution context for agent '%s' (Session: %s).",
                    skill_id, agent_id, session_id)
        return ctx

    def evict_skill_context(self, session_id: str, agent_id: str, skill_id: str) -> None:
        """Eviction: Removes procedural guidance from agent memory once work is completed."""
        context_key = f"{session_id}::{agent_id}::{skill_id}"
        if context_key in self._active_contexts:
            self._active_contexts[context_key].evict()
            del self._active_contexts[context_key]
            self._log_audit("SKILL_EVICTED", {
                "skill_id": skill_id,
                "agent_id": agent_id,
                "session_id": session_id
            })

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return list(self._audit_log)