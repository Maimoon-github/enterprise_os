export default function AgentsFleetPage() {
  const agents = [
    { name: "Master Orchestrator (Supervisor)", model: "ollama:llama3.3:70b", role: "Routing, State & Approval Governance" },
    { name: "Research & Recon Specialist", model: "ollama:qwen2.5:14b", role: "Market Intelligence, Competitor Analysis" },
    { name: "Creative Blueprint Architect", model: "ollama:llama3.3:70b", role: "Copy Synthesis, Voice Consistency" },
    { name: "Platform Fan-Out Publisher", model: "ollama:qwen2.5:14b", role: "Map-Reduce Publishing to 8 Channels" },
    { name: "Closed-Loop Analytics Judge", model: "ollama:qwen2.5:14b", role: "ReWOO Metric Anomaly Detection" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Agent Fleet Configuration</h1>
        <p className="text-slate-400 text-sm">Inspect agent personas, local Ollama model assignments, and tool scopes.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {agents.map((agent) => (
          <div key={agent.name} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-white text-base">{agent.name}</h3>
              <span className="text-xs font-mono bg-slate-950 px-2 py-0.5 rounded text-indigo-400 border border-slate-800">
                {agent.model}
              </span>
            </div>
            <p className="text-xs text-slate-400">{agent.role}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
