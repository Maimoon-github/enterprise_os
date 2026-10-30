export default function SettingsPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Platform Configuration & Secrets</h1>
        <p className="text-slate-400 text-sm">Manage encrypted platform OAuth tokens, Celery worker concurrency, and Podman sandboxes.</p>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <h3 className="text-base font-semibold text-white">Social Platform Integrations</h3>
        <p className="text-xs text-slate-400">All credentials stored encrypted with AES-256-GCM via SocialGateway FastMCP server.</p>
        <div className="grid grid-cols-2 gap-3 text-xs">
          {["LinkedIn API", "YouTube Data API", "Meta Graph API (IG/FB/Threads)", "X API v2", "Pinterest REST v5", "Google Business Profile"].map((c) => (
            <div key={c} className="p-3 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-between">
              <span>{c}</span>
              <span className="text-emerald-400 font-semibold">Configured</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
