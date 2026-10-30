export function ToolCallInspector({ toolCall }: { toolCall?: any }) {
  if (!toolCall) return <div className="text-xs text-slate-500">No active tool call inspected.</div>;
  return (
    <div className="p-3 bg-slate-950 border border-slate-800 rounded text-xs font-mono">
      <div className="text-indigo-400 font-semibold">{toolCall.tool}</div>
      <pre className="mt-2 text-slate-300">{JSON.stringify(toolCall.args, null, 2)}</pre>
    </div>
  );
}
