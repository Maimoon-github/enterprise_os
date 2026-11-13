import { PageHeaderSkeleton, Skeleton, TableSkeleton } from "@/components/page/Skeletons";

// The LinkedIn layout already pads the page, so this composes the skeleton
// pieces rather than using ListPageSkeleton (which adds PageContainer).
export default function SearchLoading() {
  return (
    <div aria-busy="true" aria-label="Loading" className="mx-auto w-full max-w-[1440px] space-y-6">
      <PageHeaderSkeleton />
      <div className="rounded-2xl bg-bg-weak-50 p-1 ring-1 ring-inset ring-stroke-soft-200">
        <div className="space-y-1.5 px-4 pb-3 pt-3">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-3 w-96 max-w-full" />
        </div>
        <div className="grid grid-cols-2 gap-x-5 gap-y-5 rounded-xl bg-bg-white-0 p-5 ring-1 ring-inset ring-stroke-soft-200 sm:gap-x-8 lg:grid-cols-4">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="space-y-2">
              <div className="flex justify-between gap-3">
                <Skeleton className="h-3.5 w-28" />
                <Skeleton className="h-3.5 w-14" />
              </div>
              <Skeleton className="h-2 w-full" />
            </div>
          ))}
        </div>
      </div>
      <TableSkeleton rows={6} columns={5} />
    </div>
  );
}
