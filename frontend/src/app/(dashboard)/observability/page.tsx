export default function ObservabilityPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Observability & Evaluations</h1>
          <p className="text-slate-400 text-sm">OpenTelemetry distributed traces exported to self-hosted Langfuse.</p>
        </div>
        <a
          href="http://localhost:3001"
          target="_blank"
          rel="noreferrer"
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
        >
          Open Langfuse Console ↗
        </a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs uppercase font-semibold text-slate-400">Semantic Conventions</span>
          <p className="text-base font-semibold mt-2 text-white">OpenInference Span Kinds</p>
          <p className="text-xs text-slate-500 mt-1">AGENT, CHAIN, LLM, TOOL, RETRIEVER</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs uppercase font-semibold text-slate-400">Trajectory Gate</span>
          <p className="text-base font-semibold mt-2 text-emerald-400">100% Valid Order</p>
          <p className="text-xs text-slate-500 mt-1">Retrieval $\prec$ Draft $\prec$ Approval</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs uppercase font-semibold text-slate-400">Brand Voice Rubric</span>
          <p className="text-base font-semibold mt-2 text-emerald-400">0.92 Average Score</p>
          <p className="text-xs text-slate-500 mt-1">Evaluated by isolated LLM judge</p>
        </div>
      </div>
    </div>
  );
}
