import { KpiStripSkeleton, PageHeaderSkeleton, Skeleton } from "@/components/page/Skeletons";

// DetailPageSkeleton's shape without its PageContainer: the layout
// already pads the page. The body mirrors the Overview tab (KPIs, then charts).
export default function WhatsappCampaignDetailLoading() {
  return (
    <div aria-busy="true" aria-label="Loading" className="mx-auto w-full max-w-[1440px] space-y-6">
      <PageHeaderSkeleton back />
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-stroke-soft-200 ring-1 ring-inset ring-stroke-soft-200 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
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
      <KpiStripSkeleton cells={5} />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <Skeleton className="h-72 rounded-2xl lg:col-span-8" />
        <Skeleton className="h-72 rounded-2xl lg:col-span-4" />
      </div>
    </div>
  );
}
