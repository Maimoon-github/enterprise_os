export default async function RunExecutionPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Live LangGraph Execution</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight">Run {runId}</h1>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 className="text-sm font-semibold uppercase text-slate-400 mb-4 tracking-wider">LangGraph Execution DAG</h2>
        <div className="flex items-center justify-between p-4 bg-slate-950 rounded-lg border border-slate-800 font-mono text-xs overflow-x-auto">
          <div className="p-3 bg-slate-800 border border-slate-700 rounded text-center">
            Supervisor Router
          </div>
          <span>──►</span>
          <div className="p-3 bg-slate-800 border border-slate-700 rounded text-center">
            Research & Strategy (ReAct)
          </div>
          <span>──►</span>
          <div className="p-3 bg-slate-800 border border-slate-700 rounded text-center">
            Campaign Creative (Plan-Solve)
          </div>
          <span>──►</span>
          <div className="p-3 bg-amber-950/40 border border-amber-600 rounded text-center text-amber-300">
            Approval Gate (interrupt)
          </div>
          <span>──►</span>
          <div className="p-3 bg-slate-800 border border-slate-700 rounded text-center">
            Fan-Out Map (8 Platforms)
          </div>
        </div>
      </div>
    </div>
  );
}
