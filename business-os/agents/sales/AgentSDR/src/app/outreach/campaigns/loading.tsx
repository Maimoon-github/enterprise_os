import { ListPageSkeleton } from "@/components/page/Skeletons";

export default function Loading() {
  return <ListPageSkeleton kpis={4} rows={6} columns={5} avatar />;
}
