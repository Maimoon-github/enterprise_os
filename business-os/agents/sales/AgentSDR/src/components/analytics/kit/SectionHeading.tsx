/**
 * A small titled divider between groups of cards inside one view ("Calls",
 * "Messages"): an uppercase label, an optional one-line description, and a
 * hairline that fills the rest of the row. Spans the whole grid.
 *
 * Props: `title`, `description`, `className` (grid placement, default full row).
 */
export function SectionHeading({ title, description, className }: { title: string; description?: string; className?: string }) {
  return (
    <div className={className ?? "lg:col-span-12"}>
      <div className="flex items-center gap-3">
        <h2 className="text-subheading-xs uppercase text-text-sub-600">{title}</h2>
        <span aria-hidden="true" className="h-px flex-1 bg-stroke-soft-200" />
      </div>
      {description && <p className="mt-1 text-paragraph-xs text-text-sub-600">{description}</p>}
    </div>
  );
}
