import Link from "next/link";

export function CampaignList({ campaigns }: { campaigns: any[] }) {
  return (
    <div className="divide-y divide-slate-800">
      {campaigns.map((c) => (
        <div key={c.id} className="py-3 flex items-center justify-between">
          <span className="text-sm font-medium text-white">{c.name}</span>
          <Link href={`/campaigns/${c.id}`} className="text-xs text-indigo-400">View →</Link>
        </div>
      ))}
    </div>
  );
}
