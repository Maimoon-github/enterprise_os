export function GraphVisualizer({ currentNode }: { currentNode?: string }) {
  const nodes = [
    { id: "supervisor", label: "Supervisor Router" },
    { id: "research", label: "Research Subgraph" },
    { id: "creative", label: "Creative Subgraph" },
    { id: "approval", label: "Approval Gate" },
    { id: "fanout", label: "Fanout Publisher" },
  ];

  return (
    <div className="flex items-center gap-3 p-4 bg-slate-950 border border-slate-800 rounded-lg overflow-x-auto text-xs">
      {nodes.map((n, i) => (
        <div key={n.id} className="flex items-center gap-2">
          <div className={`p-2 rounded border ${currentNode === n.id ? "border-indigo-500 bg-indigo-950/40 text-white" : "border-slate-800 bg-slate-900 text-slate-400"}`}>
            {n.label}
          </div>
          {i < nodes.length - 1 && <span className="text-slate-600">→</span>}
        </div>
      ))}
    </div>
  );
}
