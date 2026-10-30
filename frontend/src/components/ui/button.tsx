export function Button({
  children,
  onClick,
  variant = "primary",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "outline" | "crimson" | "emerald";
}) {
  const styles = {
    primary:
      "glass-emerald text-bloodstone-text font-semibold hover:border-bloodstone-mint active:scale-[0.98]",
    emerald:
      "glass-emerald text-bloodstone-text font-semibold hover:border-bloodstone-mint active:scale-[0.98]",
    crimson:
      "glass-crimson text-bloodstone-text font-semibold hover:border-rose-400 active:scale-[0.98]",
    secondary:
      "bg-glass-base hover:bg-glass-elevated border border-glass-subtle text-bloodstone-text font-medium active:scale-[0.98]",
    outline:
      "border border-glass-specular text-bloodstone-mint hover:bg-glass-base active:scale-[0.98]",
  };

  return (
    <button
      onClick={onClick}
      className={`px-3.5 py-1.5 rounded-lg text-xs transition-all duration-normal ease-out-expo ${styles[variant]}`}
    >
      {children}
    </button>
  );
}
