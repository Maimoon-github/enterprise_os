export function AgentCard({ agent }: { agent: any }) {
  return (
    <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
      <div className="text-sm font-semibold text-white">{agent.name}</div>
      <div className="text-xs text-indigo-400 font-mono">{agent.model}</div>
      <p className="text-xs text-slate-400">{agent.role}</p>
    </div>
  );
}
