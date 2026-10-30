export function StatusBadge({ status }: { status: string }) {
  const isPositive =
    status === "published" || status === "completed" || status === "active" || status === "healthy";
  const isPending = status === "pending" || status === "awaiting_decision";
  const isAlert = status === "failed" || status === "rejected" || status === "error";

  let colorStyle = "bg-glass-base text-bloodstone-text-muted border-glass-subtle";
  if (isPositive) {
    colorStyle = "bg-glass-emerald text-bloodstone-mint border-glass-specular shadow-bloodstone-glow";
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
