interface ToolCallInspectorProps {
  toolCall?: {
    tool: string;
    args?: Record<string, unknown>;
  } | null;
}

export function ToolCallInspector({ toolCall }: ToolCallInspectorProps) {
  if (!toolCall) {
    return (
      <div className="p-4 glass-panel rounded-lg text-xs text-bloodstone-text-muted">
        No active tool call inspected. Scoped subgraph handoffs will appear here during execution.
      </div>
    );
  }

  return (
    <div className="p-4 glass-panel rounded-lg text-xs font-mono space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-bloodstone-mint font-semibold">{toolCall.tool}</span>
        <span className="text-[10px] px-2 py-0.5 rounded bg-glass-emerald text-bloodstone-mint border border-glass-specular">
          Injected Tool Call
        </span>
      </div>
      <pre className="p-3 bg-bloodstone-canvas/60 border border-glass-dark rounded text-bloodstone-text overflow-x-auto text-[11px] scrollbar-thin">
        {JSON.stringify(toolCall.args || {}, null, 2)}
      </pre>
    </div>
  );
}
