import Link from "next/link";

export default function CampaignsPage() {
  const campaigns = [
    { id: "c1", name: "Q4 Autonomous Platform Launch", brand: "Apex Horizon", status: "review", platforms: 8 },
    { id: "c2", name: "B2B Thought Leadership Series", brand: "Apex Horizon", status: "published", platforms: 4 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Campaign Blueprints</h1>
          <p className="text-slate-400 text-sm">Design, inspect, and execute multi-channel marketing campaigns.</p>
        </div>
        <Link
          href="/campaigns/new"
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
        >
          New Campaign
        </Link>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-xs uppercase">
            <tr>
              <th className="px-6 py-3">Campaign Name</th>
              <th className="px-6 py-3">Brand</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3">Target Platforms</th>
              <th className="px-6 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {campaigns.map((camp) => (
              <tr key={camp.id} className="hover:bg-slate-800/50">
                <td className="px-6 py-4 font-medium text-white">{camp.name}</td>
                <td className="px-6 py-4 text-slate-400">{camp.brand}</td>
                <td className="px-6 py-4">
                  <span className="px-2.5 py-1 text-xs rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    {camp.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-slate-400">{camp.platforms} Connected</td>
                <td className="px-6 py-4 text-right">
                  <Link href={`/campaigns/${camp.id}`} className="text-indigo-400 hover:text-indigo-300 text-xs font-semibold">
                    Inspect Blueprint →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
