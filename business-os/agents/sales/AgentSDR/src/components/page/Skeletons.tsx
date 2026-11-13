import { cn } from "@/utils/cn";
import { PageContainer } from "./PageHeader";

/**
 * Loading skeletons in the page layout's own shapes, so a route's
 * `loading.tsx` (and a client list's first fetch) holds the layout still
 * instead of flashing a spinner. Pulse, soft fill, no shimmer.
 *
 * - Skeleton: one block; size it with className.
 * - PageHeaderSkeleton, KpiStripSkeleton, TableSkeleton (rows inside a Frame)
 * - ListPageSkeleton: header + optional KPI strip + a table frame
 * - DetailPageSkeleton: back link + header + stat row + tabs + two frames
 * - SplitPaneSkeleton: an inbox (list pane + reading pane)
 */

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-md bg-bg-weak-50", className)} />;
}

export function PageHeaderSkeleton({ back = false, action = true }: { back?: boolean; action?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="space-y-2">
        {back && <Skeleton className="h-3 w-24" />}
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>
      {action && <Skeleton className="h-9 w-32 rounded-lg" />}
    </div>
  );
}

export function KpiStripSkeleton({ cells = 4 }: { cells?: number }) {
  return (
    <div className="rounded-2xl bg-bg-weak-50 p-1 ring-1 ring-inset ring-stroke-soft-200">
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-stroke-soft-200 lg:grid-cols-[repeat(var(--cols),minmax(0,1fr))]" style={{ "--cols": cells } as React.CSSProperties}>
        {Array.from({ length: cells }, (_, i) => (
          <div key={i} className="space-y-3 bg-bg-white-0 p-5">
            <Skeleton className="size-8 rounded-lg" />
            <Skeleton className="h-3.5 w-24" />
            <Skeleton className="h-7 w-20" />
            <Skeleton className="h-3 w-32" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 8, columns = 5, avatar = true }: { rows?: number; columns?: number; avatar?: boolean }) {
  return (
    <div className="rounded-2xl bg-bg-weak-50 p-1 ring-1 ring-inset ring-stroke-soft-200">
      <div className="flex items-center justify-between px-4 pb-3 pt-3">
        <div className="space-y-1.5">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-3 w-48" />
        </div>
        <Skeleton className="h-8 w-56 rounded-lg" />
      </div>
      <div className="rounded-xl bg-bg-white-0 p-2 ring-1 ring-inset ring-stroke-soft-200">
        <Skeleton className="h-9 w-full rounded-lg" />
        <div className="mt-1 divide-y divide-stroke-soft-200">
          {Array.from({ length: rows }, (_, r) => (
            <div key={r} className="flex items-center gap-4 px-4 py-3.5">
              <div className="flex min-w-0 flex-2 items-center gap-3">
                {avatar && <Skeleton className="size-9 shrink-0 rounded-full" />}
                <div className="min-w-0 flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-3/5" />
                  <Skeleton className="h-3 w-2/5" />
                </div>
              </div>
              {Array.from({ length: Math.max(columns - 1, 0) }, (_, c) => (
                <Skeleton key={c} className="h-3.5 flex-1" />
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ListPageSkeleton({ kpis = 0, rows = 8, columns = 5, avatar = true }: { kpis?: number; rows?: number; columns?: number; avatar?: boolean }) {
  return (
    <PageContainer>
      <div aria-busy="true" aria-label="Loading" className="space-y-6">
        <PageHeaderSkeleton />
        {kpis > 0 && <KpiStripSkeleton cells={kpis} />}
        <TableSkeleton rows={rows} columns={columns} avatar={avatar} />
      </div>
    </PageContainer>
  );
}

export function DetailPageSkeleton({ stats = 4 }: { stats?: number }) {
  return (
    <PageContainer>
      <div aria-busy="true" aria-label="Loading" className="space-y-6">
        <PageHeaderSkeleton back />
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-stroke-soft-200 ring-1 ring-inset ring-stroke-soft-200 lg:grid-flow-col lg:grid-cols-none lg:auto-cols-fr">
          {Array.from({ length: stats }, (_, i) => (
            <div key={i} className="flex items-center gap-3 bg-bg-white-0 px-4 py-3">
              <Skeleton className="size-8 rounded-lg" />
              <div className="space-y-1.5">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-4 w-12" />
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-5 border-b border-stroke-soft-200 pb-3">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-20" />
        </div>
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
          <Skeleton className="h-72 rounded-2xl lg:col-span-5" />
          <Skeleton className="h-72 rounded-2xl lg:col-span-7" />
        </div>
      </div>
    </PageContainer>
  );
}

export function SplitPaneSkeleton({ rows = 9 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="flex h-full min-h-0 flex-col">
      <div className="px-4 pt-5 sm:px-6 lg:px-8">
        <PageHeaderSkeleton action={false} />
      </div>
      <div className="mt-5 flex min-h-0 flex-1 gap-0 px-4 pb-5 sm:px-6 lg:px-8">
        <div className="flex w-full max-w-sm flex-col rounded-l-2xl bg-bg-white-0 ring-1 ring-inset ring-stroke-soft-200">
          <div className="space-y-2 border-b border-stroke-soft-200 p-3">
            <Skeleton className="h-8 w-full rounded-lg" />
            <Skeleton className="h-7 w-2/3 rounded-lg" />
          </div>
          <div className="flex-1 divide-y divide-stroke-soft-200 overflow-hidden">
            {Array.from({ length: rows }, (_, i) => (
              <div key={i} className="flex gap-3 p-3">
                <Skeleton className="size-9 shrink-0 rounded-full" />
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex justify-between gap-3">
                    <Skeleton className="h-3.5 w-1/2" />
                    <Skeleton className="h-3 w-8" />
                  </div>
                  <Skeleton className="h-3 w-4/5" />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="hidden flex-1 rounded-r-2xl bg-bg-weak-50 ring-1 ring-inset ring-stroke-soft-200 md:block" />
      </div>
    </div>
  );
}
