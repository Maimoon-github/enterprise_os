import { KpiStripSkeleton, PageHeaderSkeleton, TableSkeleton } from "@/components/page/Skeletons";

// The LinkedIn layout already pads the page, so this is ListPageSkeleton's
// content without its PageContainer.
export default function CampaignsLoading() {
  return (
    <div aria-busy="true" aria-label="Loading" className="mx-auto w-full max-w-[1440px] space-y-6">
      <PageHeaderSkeleton />
      <KpiStripSkeleton cells={5} />
      <TableSkeleton rows={8} columns={7} />
    </div>
  );
}
