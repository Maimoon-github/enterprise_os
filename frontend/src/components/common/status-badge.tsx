export function StatusBadge({ status }: { status: string }) {
  const norm = (status || "").toLowerCase();

  const isVerifiedPublished = norm === "verified_published" || norm === "published" || norm === "completed" || norm === "active" || norm === "healthy";
  const isSandbox = norm === "sandbox_only" || norm === "sandbox_restricted";
  const isUnverified = norm === "published_unverified" || norm === "awaiting_verification";
  const isPending = norm === "pending" || norm === "awaiting_decision" || norm === "running";
  const isAlert = norm === "failed" || norm === "rejected" || norm === "error" || norm === "rate_limited";

  let colorStyle = "bg-glass-base text-bloodstone-text-muted border-glass-subtle";
  if (isVerifiedPublished) {
    colorStyle = "bg-glass-emerald text-bloodstone-mint border-glass-specular shadow-bloodstone-glow";
  } else if (isSandbox) {
    colorStyle = "bg-sky-950/40 text-sky-300 border-sky-600/40";
  } else if (isUnverified) {
    colorStyle = "bg-amber-950/40 text-amber-300 border-amber-600/40";
  } else if (isPending) {
    colorStyle = "bg-glass-base text-bloodstone-mint border-bloodstone-mint/40";
  } else if (isAlert) {
    colorStyle = "bg-glass-crimson text-bloodstone-text border-border-crimson shadow-crimson-glow";
  }

  return (
    <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border backdrop-blur-sm transition-all duration-fast ${colorStyle}`}>
      {status}
    </span>
  );
}
