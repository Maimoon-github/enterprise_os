interface ToolCallInspectorProps {
  toolCall?: {
    tool: string;
    args?: Record<string, unknown>;
  } | null;
}

export function ToolCallInspector({ toolCall }: ToolCallInspectorProps) {
  if (!toolCall) {
    return (
      <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-500">
        No active tool call inspected. Scoped subgraph handoffs will appear here during execution.
      </div>
    );
  }

  return (
    <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-indigo-400 font-semibold">{toolCall.tool}</span>
        <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
          Injected Tool Call
        </span>
      </div>
      <pre className="p-3 bg-slate-900 border border-slate-800 rounded text-slate-300 overflow-x-auto text-[11px]">
        {JSON.stringify(toolCall.args || {}, null, 2)}
      </pre>
    </div>
  );
}
