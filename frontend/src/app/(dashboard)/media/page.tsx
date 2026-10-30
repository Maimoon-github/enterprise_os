export default function MediaStudioPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Media Studio & Asset Storage</h1>
          <p className="text-slate-400 text-sm">MinIO-backed asset library and AI generation job pipeline.</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition">
          Upload Raw Asset
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {["1:1 Square Feed (Instagram/LinkedIn)", "9:16 Vertical Reel (YouTube Shorts/Reels)", "16:9 Landscape Video (YouTube)"].map((slot) => (
          <div key={slot} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="h-36 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-center text-xs text-slate-500 font-mono">
              MinIO Asset Preview
            </div>
            <div className="text-sm font-medium text-white">{slot}</div>
            <div className="text-xs text-slate-400">Content Hash: <span className="font-mono text-slate-300">sha256_8f92a1...</span></div>
          </div>
        ))}
      </div>
    </div>
  );
}
