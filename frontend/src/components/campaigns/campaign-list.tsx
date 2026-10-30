import Link from "next/link";

export function CampaignList({ campaigns }: { campaigns: any[] }) {
  return (
    <div className="divide-y divide-glass-dark">
      {campaigns.map((c) => (
        <div key={c.id} className="py-3 flex items-center justify-between">
          <span className="text-sm font-medium text-bloodstone-text">{c.name}</span>
          <Link href={`/campaigns/${c.id}`} className="text-xs text-bloodstone-mint hover:underline">
            View →
          </Link>
        </div>
      ))}
    </div>
  );
}
