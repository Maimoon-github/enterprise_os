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

  return (
    <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase font-bold text-amber-400 tracking-wider">
            Awaiting Decision • {approval.step_name}
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
            Thread {approval.thread_id}
          </span>
        </div>
        <div className="text-sm font-semibold text-white">
          {blueprint.objective || `Run ${approval.run_id}`}
        </div>
        <div className="text-xs text-slate-400">
          {assetsCount > 0
            ? `${assetsCount} platform assets staged for review.`
            : "Platform assets staged with SHA-256 idempotency validation."}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {onInspectDiff && (
          <button
            onClick={() => onInspectDiff(approval)}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 rounded font-medium transition"
          >
            Inspect Blueprint Diff
          </button>
        )}
        <button
          onClick={() => onReject(approval.id)}
          className="px-3 py-1.5 bg-rose-950/60 hover:bg-rose-900/80 border border-rose-800 text-xs text-rose-200 rounded font-medium transition"
        >
          Request Revision
        </button>
        <button
          onClick={() => onApprove(approval.id)}
          className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-xs text-white rounded font-medium shadow transition"
        >
          Approve & Publish
        </button>
      </div>
    </div>
  );
}
