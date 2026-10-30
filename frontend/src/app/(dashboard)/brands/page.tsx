export default function BrandsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Brand Workspaces</h1>
          <p className="text-slate-400 text-sm">Define voice guidelines, messaging pillars, and target customer profiles.</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition">
          New Brand
        </button>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-white">Apex Horizon</h3>
          <span className="text-xs bg-indigo-500/10 text-indigo-400 px-2.5 py-1 rounded-full border border-indigo-500/20">Active Workspace</span>
        </div>
        <p className="text-sm text-slate-300">
          Tone: High-agency, precise, zero buzzwords, data-backed proof. Focuses on B2B Tech Leaders and autonomous operations.
        </p>
        <div className="flex gap-2">
          {["linkedin", "x", "youtube", "threads", "instagram", "facebook", "pinterest", "google_business_profile"].map((plat) => (
            <span key={plat} className="text-xs bg-slate-950 px-2 py-1 rounded text-slate-400 border border-slate-800 font-mono">
              {plat}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
