export function AssetGrid({ assets }: { assets: any[] }) {
  return (
    <div className="grid grid-cols-3 gap-4">
      {assets.map((a, i) => (
        <div key={i} className="p-3 bg-slate-900 border border-slate-800 rounded-lg">
          <div className="h-28 bg-slate-950 rounded flex items-center justify-center text-xs text-slate-500">Asset</div>
          <div className="mt-2 text-xs font-mono text-slate-300">{a.content_hash?.slice(0, 12)}</div>
        </div>
      ))}
    </div>
  );
}
