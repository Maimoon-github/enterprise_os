import { KpiStripSkeleton, PageHeaderSkeleton, Skeleton, TableSkeleton } from "@/components/page/Skeletons";
import { PageContainer } from "@/components/page/PageHeader";

/**
 * Loading shapes for the CRM pages, built from the page kit's Skeleton so a
 * route's `loading.tsx` and the client's first fetch draw the same layout.
 * The `*Body` variants carry no PageContainer: the client renders them inside
 * the one CrmLayout already provides.
 */

/** Skeleton rows for a CRM table inside an existing FramePanel. */
export function RowsSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="divide-y divide-stroke-soft-200">
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="flex items-center gap-4 px-4 py-3.5">
          <div className="flex w-[22%] min-w-40 items-center gap-3">
            <Skeleton className="size-9 shrink-0 rounded-full" />
            <div className="min-w-0 flex-1 space-y-1.5">
              <Skeleton className="h-3.5 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
          <Skeleton className="hidden h-6 w-24 rounded-md sm:block" />
          <div className="hidden flex-1 space-y-1.5 md:block">
            <Skeleton className="h-3.5 w-11/12" />
            <Skeleton className="h-3 w-16" />
          </div>
          <div className="hidden flex-1 space-y-1.5 lg:block">
            <Skeleton className="h-3.5 w-4/5" />
            <Skeleton className="h-3 w-24" />
          </div>
          <Skeleton className="ml-auto h-5 w-20 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function ActionsPageSkeleton() {
  return (
    <PageContainer>
      <div aria-busy="true" aria-label="Loading" className="space-y-6">
        <PageHeaderSkeleton />
        <KpiStripSkeleton cells={4} />
        <TableSkeleton rows={8} columns={5} />
      </div>
    </PageContainer>
  );
}

function CardSkeleton() {
  return (
    <div className="space-y-3 rounded-xl bg-bg-white-0 p-3.5 ring-1 ring-inset ring-stroke-soft-200">
      <div className="flex items-center gap-3">
        <Skeleton className="size-8 shrink-0 rounded-full" />
        <div className="min-w-0 flex-1 space-y-1.5">
          <Skeleton className="h-3.5 w-2/3" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      </div>
      <Skeleton className="h-6 w-24 rounded-md" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-4/5" />
    </div>
  );
}

/** The pipeline board: three stage columns of cards. */
export function BoardSkeleton({ cards = 4 }: { cards?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="grid grid-cols-1 gap-4 lg:grid-cols-3 lg:gap-5">
      {Array.from({ length: 3 }, (_, c) => (
        <div key={c} className={c > 0 ? "hidden rounded-2xl bg-bg-weak-50 p-1 ring-1 ring-inset ring-stroke-soft-200 lg:block" : "rounded-2xl bg-bg-weak-50 p-1 ring-1 ring-inset ring-stroke-soft-200"}>
          <div className="flex items-center justify-between px-3 pb-3 pt-3">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-4 w-8" />
          </div>
          <div className="space-y-2">
            {Array.from({ length: cards }, (_, i) => <CardSkeleton key={i} />)}
          </div>
        </div>
      ))}
    </div>
  );
}

export function PipelinePageSkeleton() {
  return (
    <PageContainer>
      <div aria-busy="true" aria-label="Loading" className="space-y-6">
        <PageHeaderSkeleton />
        <KpiStripSkeleton cells={3} />
        <BoardSkeleton />
      </div>
    </PageContainer>
  );
}

/** Record workspace: header, stat row, reply and conversation frames. */
export function RecordBody() {
  return (
    <div aria-busy="true" aria-label="Loading" className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-3 w-28" />
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <Skeleton className="size-10 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-3.5 w-72 max-w-full" />
            </div>
          </div>
          <Skeleton className="hidden h-9 w-48 rounded-lg sm:block" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-stroke-soft-200 ring-1 ring-inset ring-stroke-soft-200 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="flex items-center gap-3 bg-bg-white-0 px-4 py-3">
            <Skeleton className="size-8 rounded-lg" />
            <div className="space-y-1.5">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-4 w-16" />
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Skeleton className="h-96 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    </div>
  );
}

export function RecordPageSkeleton() {
  return <PageContainer><RecordBody /></PageContainer>;
}

/** Sequence editor: header, stat row, details frame, timeline + steps. */
export function EditorBody() {
  return (
    <div aria-busy="true" aria-label="Loading" className="space-y-6">
      <PageHeaderSkeleton back />
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-stroke-soft-200 ring-1 ring-inset ring-stroke-soft-200 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="flex items-center gap-3 bg-bg-white-0 px-4 py-3">
            <Skeleton className="size-8 rounded-lg" />
            <div className="space-y-1.5">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-4 w-16" />
            </div>
          </div>
        ))}
      </div>
      <Skeleton className="h-36 rounded-2xl" />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <Skeleton className="h-80 rounded-2xl lg:col-span-4" />
        <div className="space-y-4 lg:col-span-8">
          <Skeleton className="h-44 rounded-2xl" />
          <Skeleton className="h-44 rounded-2xl" />
        </div>
      </div>
    </div>
  );
}

export function EditorPageSkeleton() {
  return <PageContainer><EditorBody /></PageContainer>;
}
