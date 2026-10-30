import Link from "next/link";

export default async function CampaignDetailPage({
  params,
}: {
  params: Promise<{ campaignId: string }>;
}) {
  const { campaignId } = await params;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">Campaign Blueprint</span>
          <h1 className="text-2xl font-bold tracking-tight">Campaign {campaignId}</h1>
        </div>
        <Link
          href={`/runs/run_latest_${campaignId}`}
          className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm transition"
        >
          View Live Graph Run →
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h2 className="text-base font-semibold mb-3">Positioning Brief & Strategy</h2>
            <p className="text-sm text-slate-300 leading-relaxed">
              Positioning Apex Horizon as the definitive self-hosted agentic platform. Emphasizing zero hallucinations, deterministic human approval gates, and zero-trust credential segregation.
            </p>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h2 className="text-base font-semibold mb-4">Platform Asset Matrix (8 Channels)</h2>
            <div className="space-y-3">
              {["LinkedIn (Carousel PDF)", "X (280-char Thread)", "YouTube (Shorts 9:16)", "Threads (500-char chain)"].map((p) => (
                <div key={p} className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg flex items-center justify-between">
                  <span className="text-sm font-medium">{p}</span>
                  <span className="text-xs text-emerald-400">Compliance Passed</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h2 className="text-base font-semibold mb-3">Checkpoint Status</h2>
            <div className="text-xs space-y-2 text-slate-400">
              <div>Thread: <span className="text-white font-mono">th_982348a</span></div>
              <div>State: <span className="text-amber-400">Awaiting Approval</span></div>
              <div>Checkpointer: <span className="text-white">PostgresSaver</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
