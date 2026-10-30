export function BlueprintViewer({ blueprint }: { blueprint: any }) {
  return (
    <pre className="p-4 glass-panel rounded-lg text-xs font-mono text-bloodstone-text-muted overflow-x-auto scrollbar-thin">
      {JSON.stringify(blueprint, null, 2)}
    </pre>
  );
}
