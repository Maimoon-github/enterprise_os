import { PageHeaderSkeleton, Skeleton } from "@/components/page/Skeletons";

// The wizard's shell — steps frame beside the step frame — without a
// PageContainer, since the LinkedIn layout already pads the page.
export default function NewLinkedInCampaignLoading() {
  return (
    <div aria-busy="true" aria-label="Loading" className="mx-auto w-full max-w-[1440px] space-y-6">
      <PageHeaderSkeleton back action={false} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_minmax(0,1fr)] lg:gap-5">
        <Skeleton className="h-40 rounded-2xl lg:h-80" />
        <Skeleton className="h-[560px] rounded-2xl" />
      </div>
    </div>
  );
}
