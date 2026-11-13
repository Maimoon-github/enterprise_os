import { ListPageSkeleton } from "@/components/page/Skeletons";

export default function Loading() {
  return <ListPageSkeleton kpis={3} rows={6} columns={4} avatar={false} />;
}
