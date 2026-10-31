import { ApprovalResponse } from "@marketing-os/contracts";

interface ApprovalCardProps {
  approval: ApprovalResponse;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onInspectDiff?: (approval: ApprovalResponse) => void;
}

export function ApprovalCard({
  approval,
  onApprove,
  onReject,
  onInspectDiff,
}: ApprovalCardProps) {
  const payload = (approval.payload || {}) as Record<string, any>;
  const blueprint = payload.campaign_blueprint || {};
  const assetsCount = Array.isArray(blueprint.platform_assets)
    ? blueprint.platform_assets.length
    : 0;

  const isStrategyGate = approval.step_name === "strategy_approval_gate_node";
  const isOptimizationGate = approval.step_name === "optimization_approval_gate_node";
  const gateLabel = isStrategyGate
    ? "HITL-01 • Strategy Dossier"
    : isOptimizationGate
    ? "HITL-03 • Optimization Proposal"
    : `HITL-02 • Campaign Preview`;

  const description = isStrategyGate
    ? "Market research findings, competitor positioning whitespace, and brand audience pillars staged for review."
    : isOptimizationGate
    ? "Closed-loop statistical anomaly evaluation and budget reallocation directives staged for sign-off."
    : assetsCount > 0
    ? `${assetsCount} platform assets staged with 7-stage SHA-256 idempotency validation.`
    : "Platform assets staged with SHA-256 idempotency validation.";

  const approveButtonLabel = isStrategyGate
    ? "Approve Strategy"
    : isOptimizationGate
    ? "Approve Optimization"
    : "Approve & Publish";

  return (
    <div className="p-5 glass-card flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase font-bold text-bloodstone-mint tracking-wider">
            {gateLabel}
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-glass-base border border-glass-subtle text-bloodstone-text-muted font-mono">
            Thread {approval.thread_id}
          </span>
        </div>
        <div className="text-sm font-semibold text-bloodstone-text">
          {blueprint.objective || payload.message || `Run ${approval.run_id}`}
        </div>
        <div className="text-xs text-bloodstone-text-muted leading-relaxed">
          {description}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {onInspectDiff && (
          <button
            onClick={() => onInspectDiff(approval)}
            className="px-3 py-1.5 bg-glass-base hover:bg-glass-elevated border border-glass-subtle text-xs text-bloodstone-text rounded-lg font-medium transition duration-fast ease-out-expo"
          >
            Inspect Blueprint Diff
          </button>
        )}
        <button
          onClick={() => onReject(approval.id)}
          className="px-3 py-1.5 glass-crimson text-xs rounded-lg font-medium transition duration-fast ease-out-expo"
        >
          Request Revision
        </button>
        <button
          onClick={() => onApprove(approval.id)}
          className="px-3.5 py-1.5 glass-emerald text-xs rounded-lg font-medium transition duration-fast ease-out-expo"
        >
          {approveButtonLabel}
        </button>
      </div>
    </div>
  );
}
