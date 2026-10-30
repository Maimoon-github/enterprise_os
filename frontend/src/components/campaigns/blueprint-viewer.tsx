export function BlueprintViewer({ blueprint }: { blueprint: any }) {
  return (
    <pre className="p-4 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-slate-300 overflow-x-auto">
      {JSON.stringify(blueprint, null, 2)}
    </pre>
  );
}
