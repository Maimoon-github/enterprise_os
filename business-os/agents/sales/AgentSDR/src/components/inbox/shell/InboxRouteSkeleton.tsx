import { PageHeaderSkeleton, Skeleton } from "@/components/page/Skeletons";
import { cn } from "@/utils/cn";

/**
 * Route `loading.tsx` for an inbox, shaped like the loaded page: header,
 * then the list (search, tabs, rows) beside an empty reading pane. It carries
 * the page's own padding; the LinkedIn and WhatsApp section layouts already
 * pad their `<main>`, so there (`inset`) it cancels that padding to land in
 * exactly the place the loaded page will.
 */
export function InboxRouteSkeleton({ inset = false }: { inset?: boolean }) {
  return (
    <div className={cn("h-full", inset && "-mx-4 -my-5 h-[calc(100%+2.5rem)] sm:-mx-6 sm:-my-6 sm:h-[calc(100%+3rem)] lg:-mx-8")}>
      <div aria-busy="true" aria-label="Loading" className="flex h-full min-h-0 flex-col px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
        <PageHeaderSkeleton action={false} />
        <div className="mt-4 flex min-h-0 flex-1 overflow-hidden rounded-2xl border border-stroke-soft-200 bg-bg-white-0">
          <div className="flex w-full flex-col border-stroke-soft-200 md:w-80 md:border-r xl:w-[22rem]">
            <div className="space-y-3 px-3 pb-2 pt-3">
              <Skeleton className="h-9 w-full rounded-lg" />
              <div className="flex gap-4 px-1 pb-1.5">
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-14" />
                <Skeleton className="h-4 w-16" />
              </div>
            </div>
            <div className="flex-1 overflow-hidden border-t border-stroke-soft-200 px-1.5 pt-2">
              {Array.from({ length: 8 }, (_, i) => (
                <div key={i} className="flex gap-3 py-2.5 pl-4 pr-3">
                  <Skeleton className="size-9 shrink-0 rounded-full" />
                  <div className="min-w-0 flex-1 space-y-2 pt-0.5">
                    <div className="flex justify-between gap-3">
                      <Skeleton className="h-3.5 w-1/2" />
                      <Skeleton className="h-3 w-8" />
                    </div>
                    <Skeleton className="h-3 w-4/5" />
                    {i % 2 === 0 && <Skeleton className="h-4 w-20 rounded-md" />}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="hidden flex-1 bg-bg-weak-50/60 md:block" />
        </div>
      </div>
    </div>
  );
}
