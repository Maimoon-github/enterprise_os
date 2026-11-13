import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

/**
 * One section of the settings box: a title row — title, an optional status
 * badge, a one-line description, and the section's primary action on the
 * right — above its content. Every page under /settings renders through
 * this, so sections line up with each other.
 *
 * `width="narrow"` caps forms at a readable measure; lists and tables use the
 * full width. In the pop-up the header leaves room for the close button.
 */
export function SettingsPage({
  title,
  description,
  badge,
  actions,
  width = "wide",
  children,
}: {
  title: string;
  description: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  width?: "wide" | "narrow";
  children: ReactNode;
}) {
  return (
    <section className="px-4 py-5 sm:px-6 sm:py-6 lg:px-8 lg:py-7">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between lg:group-data-modal/settings:pr-10">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-title-h6 text-text-strong-950">{title}</h2>
            {badge}
          </div>
          <div className="mt-1 max-w-2xl text-paragraph-sm text-text-sub-600">{description}</div>
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2 self-start">{actions}</div>}
      </header>
      <div className={cn(width === "narrow" && "max-w-3xl")}>{children}</div>
    </section>
  );
}
