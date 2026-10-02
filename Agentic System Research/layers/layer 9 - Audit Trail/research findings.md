### System Architecture & Engineering Specification

The **Strategy Engine (`W_STRAT`, Layer 5)** is a bounded worker agent within the Enterprise OS backend. In accordance with **Model A** invariants, it operates under zero ambient authority: it has no direct socket, network, or query access to the Central Database (CDB), Headless CMS, or Agentic RAG. All external domain signals—market dynamics from `W_COMP`, consumer sentiments from `W_VOICE`, verified clinical claims from `W_PROD`, and ROAS decay curves from `W_LEARN`—are mediated exclusively through validated, read-only context slices assembled by the **Intelligence Engine (IE, Layer 2)**.

All mathematical optimizations, econometric regressions, and Monte Carlo scenario analyses run inside ephemeral containers managed by **`agent_sandbox` (Layer 6)** under the `S_ALLOC` capability profile. These containers enforce strict system-level confinement: `DENY_ALL` network egress, syscall filtering via seccomp, memory/CPU controls via cgroups, and execution scratchpads mounted strictly on ephemeral `tmpfs`. Every strategic run, solver script invocation, and synthesized evidence envelope appends immutable W3C PROV cryptographically linked audit records to the **Immutable Ledger (Layer 9)** before generating human-in-the-loop (HITL) previews.

---

### 1. Complete File & Directory Tree

```text
enterprise_os/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   └── strategy_engine/
│   │   │       ├── subagents/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── allocation.py
│   │   │       │   ├── audience.py
│   │   │       │   ├── funnel.py
│   │   │       │   ├── media_mix.py
│   │   │       │   ├── roadmap.py
│   │   │       │   ├── scenario.py
│   │   │       │   └── synthesis.py
│   │   │       ├── __init__.py
│   │   │       ├── profiles.py
│   │   │       └── strategy.py
│   │   ├── integrations/
│   │   │   └── sandbox/
│   │   │       ├── capabilities.py
│   │   │       ├── client.py
│   │   │       └── s_alloc_core.py
│   │   ├── schemas/
│   │   │   ├── agent_contracts.py
│   │   │   ├── provenance.py
│   │   │   └── strategy.py
│   │   └── services/
│   │       └── provenance.py
│   └── tests/
│       ├── integration/
│       │   └── test_strategy_integration.py
│       ├── strategy_engine/
│       │   ├── __init__.py
│       │   ├── test_allocation.py
│       │   ├── test_audience.py
│       │   ├── test_contracts.py
│       │   ├── test_funnel.py
│       │   ├── test_ie_roundtrip.py
│       │   ├── test_media_mix.py
│       │   ├── test_profiles_and_llm_isolation.py
│       │   ├── test_provenance.py
│       │   ├── test_roadmap.py
│       │   ├── test_sandbox_security.py
│       │   ├── test_scenario.py
│       │   └── test_synthesis.py
│       └── unit/
│           ├── test_strategy_allocation_verification.py
│           └── test_strategy_contracts.py
└── sandbox/
    └── docker/
        └── hardened/
            └── skills/
                └── s-alloc/
                    ├── scripts/
                    │   ├── bayesian_mmm.py
                    │   ├── linear_solver.py
                    │   ├── monte_carlo.py
                    │   └── run.py
                    └── SKILL.md

```

---

### 2. Strategy Engine Subagent Component Matrix

| Subagent Component | Domain Role & Specialization | Inbound Inputs (IE Context Slice) | Outbound Deliverables & Artifacts | Sandbox Micro-Tools (`S_ALLOC`) | W3C PROV Lineage Entities |
| --- | --- | --- | --- | --- | --- |
| **`allocation.py`** | Budget allocation, portfolio rebalancing, and channel spend cap optimization | Portfolio budget cap, channel minimums/maximums, channel marginal ROAS curves (from `W_LEARN`) | `BudgetAllocationArtifact` (UUID-indexed spend envelopes per channel and tier) | `solve_linear_budget_allocation`, `evaluate_kkt_optimality` | `strat:BudgetAllocationEntity`, `strat:AllocationActivity` |
| **`media_mix.py`** | Econometric media mix modeling (MMM), saturation curves, and cross-channel synergy scoring | Historical spend & revenue timeseries, competitor pressure indices (from `W_COMP`), ad decay constants | `MediaMixCoefficientsArtifact` (Hill equation saturation coefficients, adstock $\alpha$, cross-channel synergies) | `estimate_bayesian_mmm`, `calculate_adstock_decay` | `strat:MediaMixArtifact`, `strat:MMMFitActivity` |
| **`funnel.py`** | Full-funnel architecture (TOFU/MOFU/BOFU), stage conversion simulation, and leak detection | Customer journey maps & dropoff rates (from `W_VOICE`), historical channel transition matrices | `FunnelArchitectureArtifact` (Stage nodes, transition probabilities, leak mitigation strategies) | `simulate_markov_funnel`, `detect_funnel_bottlenecks` | `strat:FunnelModelEntity`, `strat:FunnelSimulationActivity` |
| **`roadmap.py`** | Multi-quarter omnichannel execution sequencing, flighting calendars, and dependency graphs | Strategic objectives, creative production lead times, seasonal demand vectors | `StrategicRoadmapArtifact` (Gantt flighting calendars, milestone dependencies, release gates) | `sequence_critical_path`, `validate_flighting_constraints` | `strat:RoadmapEntity`, `strat:SequencingActivity` |
| **`audience.py`** | Segment prioritization, TAM/SAM/SOM value-tier mapping, and persona targeting matrices | Customer sentiment segments (from `W_VOICE`), competitor targeting footprints (from `W_COMP`) | `AudiencePrioritizationArtifact` (Segment scoring matrix, TAM/SAM/SOM breakdown, channel match-scores) | `score_segment_attractiveness`, `project_tam_sam_som` | `strat:AudienceMatrixEntity`, `strat:SegmentationActivity` |
| **`scenario.py`** | Monte Carlo what-if simulations, sensitivity stress-testing, and risk-weighted forecasting | Macro volatility indices, competitive response vectors, proposed budget mixes | `ScenarioRiskProfileArtifact` (Probability distribution over ROAS, Value-at-Risk [VaR], stress tests) | `run_monte_carlo_simulation`, `calculate_roas_confidence_intervals` | `strat:ScenarioDistributionEntity`, `strat:MonteCarloActivity` |
| **`synthesis.py`** | Upward synthesis of subagent deliverables into unified strategic dossiers and confidence intervals | Deliverables from all 6 upstream strategy subagents, policy governance envelopes | `StrategicDossierArtifact` (Consolidated executive strategy, unified confidence intervals, preview payload) | `reconcile_strategic_constraints`, `synthesize_confidence_bounds` | `strat:StrategicDossierEntity`, `strat:SynthesisActivity` |

---

### 3. Pydantic v2 Schema Contracts (`app/schemas/strategy.py`)

```python
"""
app/schemas/strategy.py
Data contracts for Strategy Engine (W_STRAT, Layer 5), S_ALLOC bindings, and Upward Evidence Envelopes.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Sha256Hash = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]


# --- Core Enumerations ---

class StrategicHorizon(str, Enum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"
    MULTI_QUARTER = "MULTI_QUARTER"


class MarketingChannel(str, Enum):
    META_ADS = "META_ADS"
    GOOGLE_SEARCH = "GOOGLE_SEARCH"
    GOOGLE_PERFORMANCE_MAX = "GOOGLE_PERFORMANCE_MAX"
    TIKTOK_PAID = "TIKTOK_PAID"
    LINKEDIN_PAID = "LINKEDIN_PAID"
    ORGANIC_SOCIAL = "ORGANIC_SOCIAL"
    INFLUENCER = "INFLUENCER"
    EMAIL_CRM = "EMAIL_CRM"
    CONTENT_SEO = "CONTENT_SEO"


class FunnelStage(str, Enum):
    TOFU_AWARENESS = "TOFU_AWARENESS"
    MOFU_CONSIDERATION = "MOFU_CONSIDERATION"
    BOFU_CONVERSION = "BOFU_CONVERSION"
    RETENTION_LOYALTY = "RETENTION_LOYALTY"


# --- S_ALLOC Mathematical Solver Payloads ---

class ChannelConstraintEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: MarketingChannel
    min_spend: Decimal = Field(ge=Decimal("0.00"), description="Lower spend bound.")
    max_spend: Decimal = Field(gt=Decimal("0.00"), description="Upper spend bound.")
    current_spend: Decimal = Field(ge=Decimal("0.00"), description="Baseline spend.")
    historical_roas: Decimal = Field(gt=Decimal("0.00"), description="Historical ROAS baseline.")
    marginal_decay_rate: float = Field(gt=0.0, le=1.0, description="Marginal return decay constant.")


class BudgetOptimizationParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: UUID
    optimization_run_id: UUID = Field(default_factory=uuid4)
    total_budget: Decimal = Field(gt=Decimal("0.00"))
    currency: str = Field(default="USD", max_length=3)
    target_blended_roas: Decimal = Field(gt=Decimal("0.00"))
    risk_tolerance: float = Field(ge=0.0, le=1.0, default=0.5)
    envelopes: List[ChannelConstraintEnvelope] = Field(min_length=1)


class HillSaturationParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: MarketingChannel
    half_saturation_point: float = Field(gt=0.0, description="Half-saturation spend point.")
    slope_shape: float = Field(gt=0.0, description="Hill function slope parameter.")
    adstock_decay: float = Field(ge=0.0, le=1.0, description="Geometric adstock decay factor.")
    synergy_multiplier: float = Field(ge=1.0, default=1.0, description="Cross-channel interaction boost.")


class MediaMixModelingSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parameters: List[HillSaturationParameters]
    sampling_iterations: int = Field(default=2000, ge=500, le=10000)
    convergence_r_hat_max: float = Field(default=1.05, le=1.10)
    cross_validation_mape_threshold: float = Field(default=0.12, le=0.20)


# --- Subagent Deliverables ---

class ChannelSpendAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: MarketingChannel
    allocated_spend: Decimal
    percentage_of_total: float = Field(ge=0.0, le=100.0)
    expected_incremental_revenue: Decimal
    expected_channel_roas: Decimal
    marginal_roas_at_cap: Decimal


class FunnelStageNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: FunnelStage
    target_conversion_rate: float = Field(ge=0.0, le=1.0)
    industry_benchmark_rate: float = Field(ge=0.0, le=1.0)
    transition_probability_to_next: float = Field(ge=0.0, le=1.0)
    identified_leakage_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    mitigation_tactics: List[str]


class OmnichannelMilestone(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    milestone_id: str
    quarter: str = Field(pattern=r"^Q[1-4]-(20\d\d)$")
    name: str
    flight_start_date: date
    flight_end_date: date
    assigned_channels: List[MarketingChannel]
    gating_dependencies: List[str]
    estimated_budget: Decimal


class ScenarioRiskMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_name: Literal["PESSIMISTIC_BEAR", "BASELINE_EXPECTED", "OPTIMISTIC_BULL", "BLACK_SWAN_STRESS"]
    probability: float = Field(ge=0.0, le=1.0)
    projected_roas: Decimal
    value_at_risk_95: Decimal
    expected_net_margin: Decimal
    confidence_interval_lower_95: Decimal
    confidence_interval_upper_95: Decimal


class AudienceTierSegment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str
    segment_name: str
    tier: Literal["TIER_1_CORE", "TIER_2_EXPANSION", "TIER_3_EXPLORATORY"]
    estimated_tam_size: int = Field(gt=0)
    estimated_som_target: int = Field(gt=0)
    acquisition_priority_score: float = Field(ge=0.0, le=100.0)
    primary_channels: List[MarketingChannel]


# --- S_ALLOC Raw Execution Output (Sanitized from Sandbox) ---

class SAllocExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: UUID
    solver_status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "NUMERICAL_ERROR"]
    objective_value: float
    iterations: int
    computation_time_seconds: float
    output_payload: Dict[str, Any]
    stdout_digest: Sha256Hash
    stderr_digest: Sha256Hash


# --- Upward Evidence Envelope (Conforming to Layer 2 / Layer 5 Contracts) ---

class StrategyEvidenceEnvelope(BaseModel):
    """
    Standard Upward Evidence Envelope dispatched from W_STRAT to Intelligence Engine.
    Conforms strictly to app/schemas/agent_contracts.py.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    envelope_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    tenant_id: UUID
    agent_name: Literal["strategy_engine"] = "strategy_engine"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Inbound Context Lineage Links
    consumed_context_slice_uuids: List[UUID] = Field(min_length=1)
    
    # Sandbox Lineage Links
    sandbox_execution_ids: List[UUID] = Field(min_length=1)
    solver_run_hashes: List[Sha256Hash] = Field(min_length=1)
    
    # Concrete Subagent Deliverable Payloads
    allocations: List[ChannelSpendAllocation]
    funnel_nodes: List[FunnelStageNode]
    roadmap_milestones: List[OmnichannelMilestone]
    scenario_metrics: List[ScenarioRiskMetric]
    audience_segments: List[AudienceTierSegment]
    
    # Global Decision Attributes
    overall_strategic_confidence: float = Field(ge=0.0, le=1.0)
    blended_target_roas: Decimal
    recommended_total_spend: Decimal
    
    # Layer 9 Audit Attestation
    prov_activity_id: str
    prov_signature: Sha256Hash

```

---

### 4. Sandbox Core & Capability Bindings (`Layer 6`)

#### 4.1 Interface Mapping in `app/integrations/sandbox/capabilities.py`

```python
"""
app/integrations/sandbox/capabilities.py
Registers S_ALLOC capabilities and maps W_STRAT subagents to mathematical solvers.
"""

from enum import Enum
from typing import Dict, List, Set


class SandboxCapability(str, Enum):
    S_CODE = "s_code"
    S_ALLOC = "s_alloc"
    S_COPY = "s_copy"
    S_VAL = "s_val"
    S_SCRAPE = "s_scrape"
    S_PARSE = "s_parse"
    S_ATTR = "s_attr"


# Subagent -> Allowed Micro-Tools inside S_ALLOC container
SUBAGENT_S_ALLOC_TOOL_ALLOWLIST: Dict[str, Set[str]] = {
    "allocation": {
        "solve_linear_budget_allocation",
        "evaluate_kkt_optimality",
        "rebalance_portfolio_projections",
    },
    "media_mix": {
        "estimate_bayesian_mmm",
        "calculate_adstock_decay",
        "fit_hill_saturation_curve",
    },
    "funnel": {
        "simulate_markov_funnel",
        "detect_funnel_bottlenecks",
    },
    "roadmap": {
        "sequence_critical_path",
        "validate_flighting_constraints",
    },
    "audience": {
        "score_segment_attractiveness",
        "project_tam_sam_som",
    },
    "scenario": {
        "run_monte_carlo_simulation",
        "calculate_roas_confidence_intervals",
        "evaluate_stress_matrices",
    },
    "synthesis": {
        "reconcile_strategic_constraints",
        "synthesize_confidence_bounds",
    },
}

```

#### 4.2 Adapter Implementation in `app/integrations/sandbox/s_alloc_core.py`

```python
"""
app/integrations/sandbox/s_alloc_core.py
Client adapter invoking isolated mathematical solvers inside the S_ALLOC sandbox container.
"""

import hashlib
import json
import logging
from typing import Any, Dict
from uuid import UUID, uuid4

from app.core.exceptions import SandboxSecurityViolation, SandboxSolverError
from app.integrations.sandbox.capabilities import SUBAGENT_S_ALLOC_TOOL_ALLOWLIST, SandboxCapability
from app.integrations.sandbox.client import SandboxClient
from app.schemas.strategy import SAllocExecutionResult

logger = logging.getLogger(__name__)


class SAllocCoreAdapter:
    """
    Typed invocation bridge between W_STRAT subagents and the S_ALLOC sandbox skill.
    Guarantees container parameter validation, zero network egress, and output sanitization.
    """

    def __init__(self, sandbox_client: SandboxClient):
        self._client = sandbox_client

    async def execute_solver(
        self,
        subagent_name: str,
        micro_tool_name: str,
        parameters: Dict[str, Any],
        timeout_seconds: int = 45,
    ) -> SAllocExecutionResult:
        # 1. Enforce static allowlist per subagent
        allowed_tools = SUBAGENT_S_ALLOC_TOOL_ALLOWLIST.get(subagent_name, set())
        if micro_tool_name not in allowed_tools:
            raise SandboxSecurityViolation(
                f"Subagent '{subagent_name}' is not authorized to call micro-tool '{micro_tool_name}'."
            )

        execution_id = uuid4()
        serialized_input = json.dumps(
            {
                "execution_id": str(execution_id),
                "tool": micro_tool_name,
                "parameters": parameters,
            }
        )

        logger.info(
            "Dispatching S_ALLOC solver job %s [Subagent: %s, Tool: %s]",
            execution_id,
            subagent_name,
            micro_tool_name,
        )

        # 2. Invoke Hardened Container (Egress: DENY_ALL, FS: tmpfs, seccomp: enabled)
        raw_response = await self._client.execute_skill(
            capability=SandboxCapability.S_ALLOC,
            entrypoint="scripts/run.py",
            input_data=serialized_input,
            timeout_seconds=timeout_seconds,
            env_overrides={
                "SEVAL_NETWORK_EGRESS": "DENY_ALL",
                "TMPFS_SCRATCHPAD": "/tmp/scratchpad",
                "OMP_NUM_THREADS": "2",
            },
        )

        if raw_response.exit_code != 0:
            logger.error("S_ALLOC container non-zero exit %d: %s", raw_response.exit_code, raw_response.stderr)
            raise SandboxSolverError(
                f"Mathematical solver failure in S_ALLOC (exit: {raw_response.exit_code}): {raw_response.stderr}"
            )

        # 3. Parse and sanitize isolated solver output
        try:
            parsed_output = json.loads(raw_response.stdout)
        except json.JSONDecodeError as err:
            raise SandboxSolverError("Corrupt stdout stream returned from S_ALLOC container.") from err

        stdout_hash = hashlib.sha256(raw_response.stdout.encode("utf-8")).hexdigest()
        stderr_hash = hashlib.sha256(raw_response.stderr.encode("utf-8")).hexdigest()

        return SAllocExecutionResult(
            execution_id=execution_id,
            solver_status=parsed_output.get("status", "OPTIMAL"),
            objective_value=float(parsed_output.get("objective_value", 0.0)),
            iterations=int(parsed_output.get("iterations", 0)),
            computation_time_seconds=float(parsed_output.get("elapsed_time", 0.0)),
            output_payload=parsed_output.get("data", {}),
            stdout_digest=stdout_hash,
            stderr_digest=stderr_hash,
        )

```

#### 4.3 Hardened Container Skill Definition (`sandbox/docker/hardened/skills/s-alloc/SKILL.md`)

```markdown
---
name: s-alloc
description: Ephemeral container skill executing mathematical optimization, Bayesian MMM, and Monte Carlo models.
capability: s_alloc
runtime: python:3.11-slim
security:
  network_egress: DENY_ALL
  seccomp_profile: hardened/seccomp/worker-seccomp.json
  cgroups:
    cpu_limit: "2.0"
    memory_limit: "1024M"
  filesystem:
    root: read-only
    mounts:
      - target: /tmp/scratchpad
        type: tmpfs
        options: "size=128m,mode=1777,noexec,nosuid,nodev"
---

# S_ALLOC Execution Harness

Executes mathematical formulations for `W_STRAT` subagents.

## Micro-Tools Implemented
1. `solve_linear_budget_allocation` (`scripts/linear_solver.py`): SciPy `linprog` / HiGHS interior-point solver.
2. `estimate_bayesian_mmm` (`scripts/bayesian_mmm.py`): Non-linear least squares / MCMC Hill decay saturation estimation.
3. `simulate_markov_funnel` (`scripts/monte_carlo.py`): Markov transition matrix simulation.
4. `run_monte_carlo_simulation` (`scripts/monte_carlo.py`): Vectorized NumPy stochastic ROAS sampling (100,000 iterations).

## Input/Output Protocol
- Input: JSON over STDIN.
- Output: Structured JSON payload over STDOUT.
- Diagnostics & Errors: Emitted strictly to STDERR.

```

---

### 5. Engine Implementation & Cognitive Routing

#### 5.1 Cognitive Model Routing Profiles (`app/agents/strategy_engine/profiles.py`)

```python
"""
app/agents/strategy_engine/profiles.py
Specialist subagent profiles for cognitive model routing and model tier configuration.
"""

from typing import Dict
from pydantic import BaseModel, ConfigDict


class SubagentProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    role_description: str
    model_tier: str  # e.g., "reasoning-high", "analytical-standard", "deterministic-low"
    max_tokens: int
    temperature: float
    required_context_keys: list[str]


STRATEGY_SUBAGENT_PROFILES: Dict[str, SubagentProfile] = {
    "allocation": SubagentProfile(
        name="allocation",
        role_description="Optimizes marginal ROAS and channel budget distribution under linear constraints.",
        model_tier="analytical-standard",
        max_tokens=4096,
        temperature=0.1,
        required_context_keys=["channel_telemetry", "budget_directives"],
    ),
    "media_mix": SubagentProfile(
        name="media_mix",
        role_description="Estimates adstock decay, Hill saturation curves, and cross-channel synergy weights.",
        model_tier="analytical-standard",
        max_tokens=4096,
        temperature=0.1,
        required_context_keys=["historical_spend", "competitor_intel"],
    ),
    "funnel": SubagentProfile(
        name="funnel",
        role_description="Designs full-funnel transition models, detects stage leaks, and projects drop-offs.",
        model_tier="reasoning-high",
        max_tokens=4096,
        temperature=0.2,
        required_context_keys=["journey_maps", "dropoff_telemetry"],
    ),
    "roadmap": SubagentProfile(
        name="roadmap",
        role_description="Sequences multi-quarter execution milestones, channel flighting, and release gates.",
        model_tier="reasoning-high",
        max_tokens=4096,
        temperature=0.2,
        required_context_keys=["brand_guidelines", "operational_lead_times"],
    ),
    "audience": SubagentProfile(
        name="audience",
        role_description="Prioritizes target personas, value tiers, and TAM/SAM/SOM market segments.",
        model_tier="reasoning-high",
        max_tokens=4096,
        temperature=0.3,
        required_context_keys=["sentiment_clusters", "competitor_targeting"],
    ),
    "scenario": SubagentProfile(
        name="scenario",
        role_description="Executes stochastic Monte Carlo simulations and calculates VaR risk metrics.",
        model_tier="analytical-standard",
        max_tokens=4096,
        temperature=0.1,
        required_context_keys=["volatility_metrics", "macro_conditions"],
    ),
    "synthesis": SubagentProfile(
        name="synthesis",
        role_description="Reconciles subagent deliverables into a unified strategic dossier and computes confidence bounds.",
        model_tier="reasoning-high",
        max_tokens=8192,
        temperature=0.1,
        required_context_keys=["all_subagent_artifacts"],
    ),
}

```

#### 5.2 Strategy Engine Entrypoint (`app/agents/strategy_engine/strategy.py`)

```python
"""
app/agents/strategy_engine/strategy.py
Layer 5 Strategy Engine orchestrating domain specialist subagents.
"""

import asyncio
import logging
from typing import Any, Dict
from uuid import UUID

from app.agents.strategy_engine.subagents.allocation import AllocationSubagent
from app.agents.strategy_engine.subagents.audience import AudienceSubagent
from app.agents.strategy_engine.subagents.funnel import FunnelSubagent
from app.agents.strategy_engine.subagents.media_mix import MediaMixSubagent
from app.agents.strategy_engine.subagents.roadmap import RoadmapSubagent
from app.agents.strategy_engine.subagents.scenario import ScenarioSubagent
from app.agents.strategy_engine.subagents.synthesis import SynthesisSubagent
from app.core.exceptions import StrategyExecutionError
from app.integrations.sandbox.s_alloc_core import SAllocCoreAdapter
from app.schemas.strategy import StrategyEvidenceEnvelope

logger = logging.getLogger(__name__)


class StrategyEngine:
    """
    W_STRAT Layer 5 Worker Agent.
    Coordinates the 7 domain subagents to produce complete, audited strategic recommendations.
    """

    def __init__(self, s_alloc_adapter: SAllocCoreAdapter):
        self.allocation_agent = AllocationSubagent(s_alloc_adapter)
        self.media_mix_agent = MediaMixSubagent(s_alloc_adapter)
        self.funnel_agent = FunnelSubagent(s_alloc_adapter)
        self.roadmap_agent = RoadmapSubagent(s_alloc_adapter)
        self.audience_agent = AudienceSubagent(s_alloc_adapter)
        self.scenario_agent = ScenarioSubagent(s_alloc_adapter)
        self.synthesis_agent = SynthesisSubagent(s_alloc_adapter)

    async def execute_strategy_formulation(
        self,
        task_id: UUID,
        tenant_id: UUID,
        context_slice: Dict[str, Any],
    ) -> StrategyEvidenceEnvelope:
        """
        Executes bounded strategy generation over IE-provided context slice.
        """
        logger.info("Initiating Strategy Engine formulation for task %s (tenant %s)", task_id, tenant_id)

        try:
            # Phase 1: Upstream econometric & segment foundations in parallel
            media_mix_res, audience_res = await asyncio.gather(
                self.media_mix_agent.run(context_slice),
                self.audience_agent.run(context_slice),
            )

            # Phase 2: Allocation & Funnel using foundation coefficients
            enriched_slice = {
                **context_slice,
                "mmm_coefficients": media_mix_res,
                "audience_priorities": audience_res,
            }

            allocation_res, funnel_res = await asyncio.gather(
                self.allocation_agent.run(enriched_slice),
                self.funnel_agent.run(enriched_slice),
            )

            # Phase 3: Omnichannel sequencing & Monte Carlo stress testing
            phase3_slice = {
                **enriched_slice,
                "allocations": allocation_res,
                "funnel_structure": funnel_res,
            }

            roadmap_res, scenario_res = await asyncio.gather(
                self.roadmap_agent.run(phase3_slice),
                self.scenario_agent.run(phase3_slice),
            )

            # Phase 4: Final synthesis, confidence evaluation, and dossier assembly
            synthesis_input = {
                **phase3_slice,
                "roadmap": roadmap_res,
                "scenarios": scenario_res,
            }

            evidence_envelope = await self.synthesis_agent.synthesize_envelope(
                task_id=task_id,
                tenant_id=tenant_id,
                synthesis_input=synthesis_input,
            )

            logger.info("Successfully formulated strategy envelope %s for task %s", evidence_envelope.envelope_id, task_id)
            return evidence_envelope

        except Exception as exc:
            logger.exception("Strategy formulation failed for task %s: %s", task_id, str(exc))
            raise StrategyExecutionError(f"Strategy Engine formulation halted: {str(exc)}") from exc

```

---

### 6. Layer 9 W3C PROV Audit Trail & Lineage Attestation

#### 6.1 Lineage Schema Specification (`app/schemas/provenance.py`)

Strategic operations must define a strictly typed W3C PROV graph (Entities, Activities, Agents):

```python
"""
app/schemas/provenance.py (Extensions for Strategy Engine Lineage)
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ProvAgentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    agent_id: str = "agent:w_strat:strategy_engine"
    agent_type: Literal["SoftwareAgent", "Person"] = "SoftwareAgent"
    subagent_id: Optional[str] = None


class ProvActivityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    activity_id: str
    activity_type: Literal[
        "strat:ContextIngestion",
        "strat:MMMFitting",
        "strat:LinearOptimization",
        "strat:FunnelSimulation",
        "strat:MonteCarloSampling",
        "strat:DossierSynthesis",
    ]
    started_at: datetime
    ended_at: datetime
    sandbox_execution_id: Optional[UUID] = None


class ProvEntityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    entity_id: str
    entity_type: Literal[
        "strat:ContextSlice",
        "strat:SolverOutput",
        "strat:EvidenceEnvelope",
        "strat:ActionPreview",
    ]
    artifact_uuid: Optional[UUID] = None
    content_hash_sha256: str


class ProvRelationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    relation_type: Literal["wasGeneratedBy", "used", "wasAssociatedWith", "wasDerivedFrom"]
    source_id: str
    target_id: str


class StrategyProvGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    graph_id: UUID
    task_id: UUID
    tenant_id: UUID
    agents: List[ProvAgentRecord]
    activities: List[ProvActivityRecord]
    entities: List[ProvEntityRecord]
    relations: List[ProvRelationRecord]

```

#### 6.2 Service Registration (`app/services/provenance.py`)

The provenance service persists the immutable graph to the ledger:

```python
"""
app/services/provenance.py (Strategy Engine Event Handler)
"""

from uuid import UUID
from app.schemas.provenance import StrategyProvGraph
from app.persistence.repositories.provenance import ProvenanceRepository


class ProvenanceService:
    def __init__(self, prov_repo: ProvenanceRepository):
        self._repo = prov_repo

    async def record_strategy_lineage(self, graph: StrategyProvGraph) -> str:
        """
        Commits an immutable, cryptographically chained provenance record for a strategic run.
        """
        return await self._repo.append_prov_graph(
            tenant_id=graph.tenant_id,
            task_id=graph.task_id,
            graph_payload=graph.model_dump(mode="json"),
        )

```

---

### 7. End-to-End Sandbox & Provenance Wire-Up Flow

The following lifecycle details the path of a strategy directive through the enterprise architecture:

```
[Owner Directive] 
       │ 
       ▼ (Write)
1. Intelligence Engine (Layer 2)
       │  • Assembles policy-screened context slice (Market, VoC, Product, Telemetry)
       │  • Generates Task Grant (Token budget, stop rules, S_ALLOC allowlist)
       ▼ (Bounded Grant)
2. Strategy Engine (Layer 5: W_STRAT)
       │  • Subagent Fan-Out: allocation, media_mix, funnel, roadmap, audience, scenario
       │  • Validates parameters against ChannelConstraintEnvelope
       ▼ (Invoke Solver Mandate)
3. agent_sandbox (Layer 6: S_ALLOC)
       │  • Ephemeral container launched (DENY_ALL network egress, seccomp, cgroups)
       │  • Executes solvers on tmpfs: SciPy linprog, Bayesian MMM, Monte Carlo (100k iters)
       │  • Captures raw stdout/stderr; computes SHA-256 digests
       ▼ (Sanitized Execution Result)
4. Strategy Engine (Layer 5)
       │  • Validates KKT optimality and convergence (R-hat < 1.05)
       │  • synthesis.py aggregates subagent outputs into StrategyEvidenceEnvelope
       ▼ (Evidence Envelope)
5. W3C PROV Immutable Ledger (Layer 9)
       │  • Appends Entity-Activity-Agent graph linking slice UUID, solver run, and signatures
       ▼ (Attested Evidence)
6. Intelligence Engine (Layer 2)
       │  • Evaluates Policy & Authorization Boundary (PAB)
       │  • Compiles Action Preview (spend allocation, ROAS forecast, risk bounds)
       ▼ (Action Preview)
7. HITL Gate (Layer 1)
       │  • Brand Stakeholder approves, rejects, or holds spend release

```

1. **Directive Ingestion & Model A Context Assembly**:
* The brand stakeholder submits an objective (e.g., "$1.5M Q4 omnichannel growth with ROAS $\ge 3.8$").
* The Intelligence Engine retrieves pre-computed read-only slices from the Central Database via the Governed Data Access MCP Gateway:
* Market intelligence from `W_COMP` (`slice_uuid: a1b2...`).
* Feedback and friction points from `W_VOICE` (`slice_uuid: b2c3...`).
* Verified compliance claims from `W_PROD` (`slice_uuid: c3d4...`).
* Attributed decay telemetry from `W_LEARN` (`slice_uuid: d4e5...`).


* The IE wraps these slices into a bounded task grant with strict token budgets and tool allowlists.


2. **Specialist Subagent Fan-Out & Solver Execution**:
* `W_STRAT` dispatches tasks to its subagents.
* `media_mix.py` and `allocation.py` call `SAllocCoreAdapter.execute_solver(...)`.
* The adapter verifies tool permissions against `SUBAGENT_S_ALLOC_TOOL_ALLOWLIST`.
* The `agent_sandbox` controller spins up an ephemeral `s-alloc` container:
* Network ingress/egress is strictly `DENY_ALL`.
* Kernel syscalls are gated via `worker-seccomp.json`.
* Scratch files are written to an isolated `tmpfs` RAM disk (`/tmp/scratchpad`).


* Solvers (`scripts/bayesian_mmm.py`, `scripts/linear_solver.py`, `scripts/monte_carlo.py`) run natively. Output is formatted to standard JSON on STDOUT and returned to the adapter.


3. **Deterministic Ingestion & Layer 9 Ledger Commitment**:
* The adapter calculates SHA-256 digests of STDOUT/STDERR and unpacks `SAllocExecutionResult`.
* `synthesis.py` reconciles subagent outputs, validates convergence ($R\text{-hat} \le 1.05$) and KKT optimality, and computes confidence bounds.
* `synthesis.py` builds the `StrategyEvidenceEnvelope` containing all subagent deliverables.
* The engine generates a W3C PROV graph linking:
* Input Context Entities (`strat:ContextSlice`, UUIDs).
* Execution Activities (`strat:LinearOptimization`, `strat:MonteCarloSampling`).
* Executing Agents (`agent:w_strat:allocation`, `agent:w_strat:scenario`).
* Output Deliverables (`strat:EvidenceEnvelope`).


* The provenance graph is appended to the W3C PROV Immutable Ledger (Layer 9).


4. **Action Preview & HITL Review Gate**:
* The `StrategyEvidenceEnvelope` is returned to the Intelligence Engine.
* The IE verifies cryptographic signatures and passes the envelope to `hitl_preview_generator.py`.
* An immutable `ActionPreview` is generated for the human gatekeeper, presenting:
* Channel spend distribution and caps.
* Simulated funnel conversion improvements.
* Monte Carlo VaR (95%) and risk-weighted ROAS spreads.


* Actuation via the Outbound Actuation MCP Boundary remains locked until a signed HITL approval token is registered.



---

### 8. Verification & Test Architecture Inventory

The test architecture ensures contract adherence, subagent isolation, sandbox security boundaries, and roundtrip provenance tracking.

```text
backend/tests/strategy_engine/
├── test_allocation.py
├── test_audience.py
├── test_contracts.py
├── test_funnel.py
├── test_ie_roundtrip.py
├── test_media_mix.py
├── test_profiles_and_llm_isolation.py
├── test_provenance.py
├── test_roadmap.py
├── test_sandbox_security.py
├── test_scenario.py
└── test_synthesis.py

```

#### Detailed Test Catalog & Target Assertions

| Test Module | Test Suite / Target Function | Test Scope & Core Assertions |
| --- | --- | --- |
| **`test_contracts.py`** | `TestStrategyContracts` | • Assert `BudgetOptimizationParameters` rejects negative bounds or sum of minimums exceeding total budget.<br>

<br>• Assert `StrategyEvidenceEnvelope` serialization and schema parity against `agent_contracts.py`.<br>

<br>• Validate regex enforcement on milestone quarters (`Q[1-4]-20\d\d`) and SHA-256 string constraints. |
| **`test_allocation.py`** | `TestAllocationSubagent` | • Mock `SAllocCoreAdapter`; assert subagent formats linprog bounds correctly.<br>

<br>• Verify KKT optimality check triggers fallback rebalancing if numerical tolerance exceeds $10^{-6}$.<br>

<br>• Assert spend cap sums equal total budget exactly ($\sum x_i = B$). |
| **`test_media_mix.py`** | `TestMediaMixSubagent` | • Validate estimation of Hill function saturation parameters ($K$, $S$) and adstock decay factors ($\alpha$).<br>

<br>• Assert convergence check raises `SandboxSolverError` when $R\text{-hat} > 1.05$. |
| **`test_funnel.py`** | `TestFunnelSubagent` | • Assert Markov transition matrix rows sum to $1.0 \pm 10^{-5}$.<br>

<br>• Assert automated detection flags stage leaks whenever drop-off rates exceed industry benchmarks by $>20\%$. |
| **`test_roadmap.py`** | `TestRoadmapSubagent` | • Verify topological sort of milestone execution graphs.<br>

<br>• Assert circular dependency detection raises `StrategyExecutionError`.<br>

<br>• Verify flighting calendar bounds respect operational lead times. |
| **`test_audience.py`** | `TestAudienceSubagent` | • Assert TAM $\ge$ SAM $\ge$ SOM hierarchy invariants across all segments.<br>

<br>• Validate segment prioritization scoring formula against sentiment cluster inputs. |
| **`test_scenario.py`** | `TestScenarioSubagent` | • Run Monte Carlo simulator fixture with 10,000 iterations.<br>

<br>• Assert Value-at-Risk ($VaR_{0.95}$) calculation matches analytical baseline.<br>

<br>• Validate standard deviation and confidence interval calculation ($CI_{0.95}$). |
| **`test_synthesis.py`** | `TestSynthesisSubagent` | • Assert synthesis subagent reconciles conflicting channel recommendations.<br>

<br>• Verify that missing subagent outputs prevent envelope construction.<br>

<br>• Assert unified strategic confidence score is penalized when scenario risk exceeds threshold. |
| **`test_profiles_and_llm_isolation.py`** | `TestProfilesAndLLM` | • Verify that all 7 subagents are mapped in `profiles.py` with appropriate token/temperature bounds.<br>

<br>• Assert zero subagents possess direct LLM client invocation authority without IE mediation. |
| **`test_sandbox_security.py`** | `TestSandboxSecurity` | • **Egress Deny Test**: Attempt socket connection to external IP (`8.8.8.8:53`) and DB port (`5432`) from inside `s-alloc`; assert `EPERM` / connection refused.<br>

<br>• **Filesystem Read-Only Test**: Attempt write to `/usr/local/bin` and `/var`; assert `EROFS` (Read-only file system).<br>

<br>• **tmpfs Scrubbing Test**: Assert `/tmp/scratchpad` files are destroyed upon container exit.<br>

<br>• **Subagent Tool Isolation**: Assert `funnel` subagent cannot invoke `solve_linear_budget_allocation`. |
| **`test_provenance.py`** | `TestStrategyProvenance` | • Assert all generated `StrategyEvidenceEnvelope` instances contain valid W3C PROV graphs.<br>

<br>• Verify every subagent step appends corresponding `wasAssociatedWith` and `wasGeneratedBy` triples.<br>

<br>• Assert altering an input context slice hash invalidates downstream envelope signature verification. |
| **`test_ie_roundtrip.py`** | `TestIERoundtrip` | • Full mock execution of `IntelligenceEngine -> W_STRAT -> S_ALLOC -> Provenance -> ActionPreview`.<br>

<br>• Assert the generated preview contains identical UUID references to the input context slices and sandbox execution runs.<br>

<br>• Verify that no outbound network or direct DB operations occur across the entire lifecycle. |

---

### 9. Architectural Conformance & Invariant Verification

1. **Model A Compliance**: `W_STRAT` and all 7 subagents contain zero database connection pools, zero ORM instances, and zero direct HTTP/API client libraries. Data enters strictly via read-only parameters passed by the Intelligence Engine, and exits via typed evidence envelopes.
2. **Layer 6 Isolation**: Compute-intensive algorithms run in the `s-alloc` container. The execution runtime enforces `DENY_ALL` network egress, seccomp syscall filtering, cgroup memory limits (1024M), and ephemeral tmpfs scratchpads.
3. **Layer 9 Audit Lineage**: Provenance is captured across every activity step. The resulting W3C PROV graph links the incoming context slices, the containerized solver runs, and the subagent signatures, ensuring tamper-evident accountability before any strategy reaches the HITL approval gate.