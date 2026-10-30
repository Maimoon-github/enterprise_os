export function ApprovalCard({
  approval,
  onApprove,
  onReject,
}: {
  approval: any;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}) {
  return (
    <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl flex items-center justify-between">
      <div>
        <div className="text-xs text-amber-400 font-semibold">{approval.step_name}</div>
        <div className="text-sm font-semibold text-white mt-1">Run {approval.run_id}</div>
      </div>
      <div className="flex gap-2">
        <button
          onClick={() => onReject(approval.id)}
          className="px-3 py-1.5 bg-slate-800 text-xs text-slate-300 rounded"
        >
          Reject
        </button>
        <button
          onClick={() => onApprove(approval.id)}
          className="px-3 py-1.5 bg-emerald-600 text-xs text-white rounded font-medium"
        >
          Approve
        </button>
      </div>
    </div>
  );
}
