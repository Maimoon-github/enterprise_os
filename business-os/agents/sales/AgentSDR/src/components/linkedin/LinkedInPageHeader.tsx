import type { ReactNode } from "react";

export function LinkedInPageHeader({
  title,
  description,
  actions,
  badge,
  compact = false,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
  /** Rendered beside the title — state that qualifies the page, not the section. */
  badge?: ReactNode;
  compact?: boolean;
}) {
  return (
    <header className={compact ? "mb-4" : "mb-6"}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-title-h5 text-text-strong-950">{title}</h1>
            {badge}
          </div>
          <p className="mt-1 max-w-2xl text-paragraph-sm text-text-sub-600">{description}</p>
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}
