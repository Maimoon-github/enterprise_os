export default function ApprovalsQueuePage() {
  const pendingApprovals = [
    {
      id: "appr_01",
      campaign: "Q4 Autonomous Platform Launch",
      step: "human_approval_gate",
      summary: "8 cross-platform draft assets with MinIO image renders awaiting human sign-off.",
      threadId: "th_982348a",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Human-in-the-Loop Approvals</h1>
        <p className="text-slate-400 text-sm">Review interrupted LangGraph runs, inspect diffs, and resume executions.</p>
      </div>

      <div className="space-y-4">
        {pendingApprovals.map((appr) => (
          <div key={appr.id} className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-xs uppercase font-semibold text-amber-400 tracking-wider">Awaiting Decision • {appr.step}</span>
              <h3 className="text-lg font-semibold text-white">{appr.campaign}</h3>
              <p className="text-sm text-slate-400">{appr.summary}</p>
              <div className="text-xs text-slate-500 font-mono">Thread: {appr.threadId}</div>
            </div>
            <div className="flex gap-2">
              <button className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition">
                Request Revision
              </button>
              <button className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition">
                Approve & Publish
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
