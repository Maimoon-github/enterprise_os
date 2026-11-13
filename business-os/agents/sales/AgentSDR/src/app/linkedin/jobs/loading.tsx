import { PageHeaderSkeleton, TableSkeleton } from "@/components/page/Skeletons";

export default function JobsLoading() {
  return (
    <div className="mx-auto w-full max-w-[1440px] space-y-6" aria-busy="true" aria-label="Loading">
      <PageHeaderSkeleton action={false} />
      <TableSkeleton rows={10} columns={4} />
    </div>
  );
}
