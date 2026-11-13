import { KpiStripSkeleton, Skeleton, TableSkeleton } from "@/components/page/Skeletons";

/**
 * Loading shapes for each kind of settings section, so a section's
 * `loading.tsx` (and a client section's first fetch) holds its layout still.
 * `withHeader` draws the section title row too — for route loading, where the
 * SettingsPage header has not rendered yet.
 */

function SectionHeaderSkeleton({ action = true }: { action?: boolean }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div className="space-y-2">
        <Skeleton className="h-6 w-44" />
        <Skeleton className="h-4 w-80 max-w-[70vw]" />
      </div>
      {action && <Skeleton className="hidden h-9 w-36 rounded-lg sm:block" />}
    </div>
  );
}

function SectionPad({ children }: { children: React.ReactNode }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="px-4 py-5 sm:px-6 sm:py-6 lg:px-8 lg:py-7">
      {children}
    </div>
  );
}

/** KPI strip + a table of accounts. */
export function AccountsSkeleton({ withHeader = false }: { withHeader?: boolean }) {
  const body = (
    <div aria-busy="true" aria-label="Loading" className="space-y-5">
      <KpiStripSkeleton cells={4} />
      <TableSkeleton rows={4} columns={5} />
    </div>
  );
  return withHeader ? (
    <SectionPad>
      <SectionHeaderSkeleton />
      {body}
    </SectionPad>
  ) : (
    body
  );
}

/** A Frame of rows: documents, instructions, columns. */
export function ListSkeleton({ rows = 5, withHeader = false, toolbar = true }: { rows?: number; withHeader?: boolean; toolbar?: boolean }) {
  const body = (
    <div aria-busy="true" aria-label="Loading" className="rounded-2xl bg-bg-weak-50 p-1 ring-1 ring-inset ring-stroke-soft-200">
      <div className="flex items-center justify-between gap-4 px-4 py-3">
        <div className="space-y-1.5">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-56 max-w-[50vw]" />
        </div>
        {toolbar && <Skeleton className="hidden h-8 w-48 rounded-lg sm:block" />}
      </div>
      <div className="divide-y divide-stroke-soft-200 rounded-xl bg-bg-white-0 ring-1 ring-inset ring-stroke-soft-200">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-4">
            <Skeleton className="size-8 shrink-0 rounded-lg" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-3.5 w-2/5" />
              <Skeleton className="h-3 w-4/5" />
            </div>
            <Skeleton className="size-7 shrink-0 rounded-lg" />
          </div>
        ))}
      </div>
    </div>
  );
  return withHeader ? (
    <SectionPad>
      <SectionHeaderSkeleton />
      {body}
    </SectionPad>
  ) : (
    body
  );
}

/** Stacked form Frames, capped at the form width. */
export function FormSkeleton({ frames = 3, withHeader = false }: { frames?: number; withHeader?: boolean }) {
  const body = (
    <div aria-busy="true" aria-label="Loading" className="max-w-3xl space-y-4">
      {Array.from({ length: frames }, (_, i) => (
        <div key={i} className="rounded-2xl bg-bg-weak-50 p-1 ring-1 ring-inset ring-stroke-soft-200">
          <div className="space-y-1.5 px-4 py-3">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-72 max-w-[60vw]" />
          </div>
          <div className="space-y-3 rounded-xl bg-bg-white-0 p-5 ring-1 ring-inset ring-stroke-soft-200">
            <Skeleton className="h-3.5 w-28" />
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
  return withHeader ? (
    <SectionPad>
      <SectionHeaderSkeleton action={false} />
      {body}
    </SectionPad>
  ) : (
    body
  );
}

/** Four collapsed category sections. */
export function CategoriesSkeleton({ withHeader = false }: { withHeader?: boolean }) {
  const body = (
    <div aria-busy="true" aria-label="Loading" className="space-y-3">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="flex items-center gap-3 rounded-2xl bg-bg-weak-50 px-4 py-4 ring-1 ring-inset ring-stroke-soft-200">
          <Skeleton className="size-5 shrink-0 rounded" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-48" />
          </div>
          <Skeleton className="h-8 w-32 rounded-lg" />
        </div>
      ))}
    </div>
  );
  return withHeader ? (
    <SectionPad>
      <SectionHeaderSkeleton action={false} />
      {body}
    </SectionPad>
  ) : (
    body
  );
}
