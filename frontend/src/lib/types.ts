/**
 * Enterprise OS TypeScript Contracts
 * Mirrored 1-to-1 from Python Pydantic schemas in backend/app/schemas/
 */

export type WorkerRole =
  | "W_DEV"
  | "W_STRAT"
  | "W_CREAT"
  | "W_PROD"
  | "W_COMP"
  | "W_VOICE"
  | "W_LEARN";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type TaskStatus =
  | "pending"
  | "granted"
  | "in_progress"
  | "completed"
  | "failed"
  | "rejected"
  | "revised"
  | "held";

export type ActionPreviewKind =
  | "spend"
  | "live_code_diff"
  | "claims_dossier"
  | "copy_pack"
  | "attribution"
  | "general";

export interface TenantScope {
  tenant_id: string;
  brand_ids: string[];
  allowed_channels: string[];
}

export interface Directive {
  directive_id: string;
  tenant_id: string;
  objective: string;
  budget_cap: number;
  risk_ceiling: RiskLevel;
  scope: TenantScope;
  created_at?: string;
  intelligence?: IntelligenceResult;
}

export interface PlanStep {
  step_id: string;
  description: string;
  recommended_worker: WorkerRole | null;
  dependencies: string[];
  context_requirements: string[];
  expected_output: string;
}

export interface IntelligenceResult {
  request_id: string;
  objective_interpretation: string;
  intent: string;
  plan: PlanStep[];
  decision?: string | null;
  context_requests: string[];
  assumptions: string[];
  rationale_summary: string;
  confidence: number;
}

export interface CanonicalTaskState {
  task_id: string;
  directive_id: string;
  worker_role: WorkerRole;
  status: TaskStatus;
  version: number;
  checkpoint_id?: string | null;
  assigned_worker_id?: string | null;
  failure_reason?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ActionPreview {
  action_preview_id: string;
  task_id: string;
  tenant_id: string;
  worker_role: WorkerRole;
  risk_level: RiskLevel;
  preview_type: ActionPreviewKind;
  summary: string;
  spend_proposal?: {
    total_spend: number;
    channel_allocations: Record<string, number>;
    marginal_roas_projection: number;
  } | null;
  claims_dossier?: {
    approved_claims: string[];
    evidence_citations: string[];
    risk_assessment: string;
  } | null;
  code_diff?: {
    file_path: string;
    diff_unified: string;
    ast_valid: boolean;
    wcag_score?: number;
  } | null;
  copy_pack?: {
    headline: string;
    body_copy: string;
    call_to_action: string;
    prohibited_terms_checked: boolean;
  } | null;
  preview_content_hash?: string;
}

export interface ApprovalDecisionRequest {
  approved: boolean;
  decision: "APPROVE" | "REJECT" | "REQUEST_REVISION" | "HOLD";
  approver: string;
  approver_role: string;
  tenant_id?: string;
  signature?: string;
  preview_content_hash?: string;
  revision_notes?: string;
  decided_at?: string;
}

export interface ProvenanceRecord {
  record_id: string;
  tenant_id: string;
  entity_id: string;
  activity: string;
  agent: string;
  record_hash: string;
  parent_hash?: string | null;
  timestamp: string;
  metadata: Record<string, any>;
}

export interface SystemServiceStatus {
  name: string;
  port: number;
  status: "healthy" | "degraded" | "offline";
  latency_ms?: number;
  details?: string;
  url?: string;
}

export interface SandboxServiceInfo {
  name: string;
  url: string;
  status: "healthy" | "offline";
  port: number;
  features: string[];
}

export interface TelemetryReceipt {
  receipt_id: string;
  tenant_id: string;
  source_id: string;
  source_account_id?: string;
  logical_event_id: string;
  content_hash: string;
  status: "accepted" | "rejected" | "quarantined";
  channel: string;
  occurred_at?: string;
  minimized_payload?: Record<string, any>;
}

export interface TelemetryHandshakeProbe {
  listener: string;
  channel: string;
  status: "ok" | "degraded" | "unreachable";
  latency_ms: number;
  probed_at: string;
  details?: string;
}

export interface ToastMessage {
  id: string;
  type: "success" | "error" | "info" | "warning";
  title: string;
  message?: string;
  hash?: string;
  timestamp: string;
}

// --- Directive Execution & Planning Trigger Types ---
export interface ExecutionTaskInfo {
  task_id: string;
  directive_id: string;
  worker_role: string;
  status: string;
  step_id: string;
}

export interface DirectiveExecutionResponse {
  directive_id: string;
  status: string;
  plan?: IntelligenceResult | null;
  tasks_created: ExecutionTaskInfo[];
  message: string;
}

// --- W_DEV Cryptographic Decision Sealing Types ---
export interface DevelopmentDecisionRequest {
  task_id: string;
  workflow_id: string;
  step_id: string;
  attempt_id: string;
  subagent_id: string;
  reviewer_id: string;
  reviewer_role?: string;
  decision: "APPROVE" | "REJECT" | "REQUEST_REVISION";
  input_snapshot_hash: string;
  output_snapshot_hash: string;
  review_dossier_hash: string;
  signature?: string;
  private_key_pem?: string;
  nonce?: string;
  version?: string;
  revision_notes?: string;
  machine_policy_allowed?: boolean;
  expires_in_seconds?: number;
}

export interface DevelopmentDecisionResponse {
  token_id: string;
  task_id: string;
  step_id: string;
  attempt_id: string;
  decision: string;
  approved: boolean;
  reviewer_id: string;
  reviewer_role: string;
  signature: string;
  created_at: string;
  expires_at: string;
}

// --- AIO Sandbox Daemon & Micro-Tools Types ---
export interface SandboxCapabilities {
  shell: boolean;
  interpreters: string[];
  browser: boolean;
  desktop: boolean;
  workspace: string;
  micro_tools: string[];
}

export interface SandboxContext {
  id: string;
  status: string;
  runtime: string;
  default_user: string;
  home_dir: string;
  workspace: string;
  limits: {
    cpus: number;
    memory_mb: number;
    pids: number;
    default_timeout_seconds: number;
  };
  network_policy: string;
  egress_proxy: string;
  services: Record<string, number>;
}

export interface SandboxCommandResult {
  command: string;
  exit_code: number;
  output: string;
  stdout: string;
  stderr: string;
  duration_ms: number;
  status: string;
}

export interface SandboxCodeResult {
  language: string;
  output: string;
  exit_code: number;
  duration_ms: number;
  status: string;
}

export interface SandboxMicroToolResult {
  tool: string;
  status: "success" | "error";
  elapsed_ms?: number;
  result?: Record<string, any>;
  error?: string;
}

// --- Production Observability & SLO Types ---
export interface ProductionSLO {
  sli_id: string;
  name: string;
  category: "directive" | "sandbox" | "hitl" | "outbound" | "telemetry" | "database_dr" | "observability_pipeline";
  target_value: number;
  actual_value: number;
  comparison: "gte" | "lte";
  compliant: boolean;
  unit: string;
  good_events: number;
  total_events: number;
  error_budget_percentage: number;
  consumed_error_budget_percentage: number;
  remaining_error_budget_percentage: number;
  burn_rate_1h: number;
  burn_rate_6h: number;
}

export interface ObservabilityPipelineStageInfo {
  stage: string;
  name: string;
  observed: boolean;
  latency_seconds: number;
}

export interface ObservabilityCompletenessRecord {
  directive_id: string;
  tenant_id: string;
  root_trace_id: string;
  stages_seen: string[];
  missing_stages: string[];
  orphan_spans_count: number;
  dropped_telemetry_count: number;
  cardinality_violations_count: number;
  complete: boolean;
  completeness_ratio: number;
}

// --- Disaster Recovery & Chaos Certification Types ---
export interface ChaosScenarioSummary {
  scenario_id: string;
  order: number;
  name: string;
  injected_failure: string;
  expected_behavior: string;
  observed_behavior: string;
  passed: boolean;
  duration_seconds: number;
}

export interface DisasterRecoveryMetrics {
  rpo_actual_seconds: number;
  rpo_target_seconds: number;
  rto_actual_seconds: number;
  rto_target_seconds: number;
  wal_vault_status: string;
  segments_count: number;
  bit_rot_tamper_detected: boolean;
  fail_closed_verified: boolean;
  acknowledgement_boundary_mutations: number;
  reconciliation_guaranteed: boolean;
}

