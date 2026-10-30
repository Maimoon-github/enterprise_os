export function AssetGrid({ assets }: { assets: any[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {assets.map((a, i) => (
        <div key={a.id || i} className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
          <div className="h-28 bg-slate-950 border border-slate-800 rounded flex items-center justify-center text-xs text-slate-500 font-mono">
            {a.minio_key || "MinIO Asset Object"}
          </div>
          <div className="text-xs font-mono text-slate-300 truncate">Hash: {a.content_hash?.slice(0, 16)}</div>
          <div className="text-xs text-slate-400">Type: <span className="text-slate-200">{a.mime_type || "image/png"}</span></div>
        </div>
      ))}
    </div>
  );
}
