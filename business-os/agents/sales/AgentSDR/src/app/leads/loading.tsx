import { ListPageSkeleton } from "@/components/page/Skeletons";

export default function Loading() {
  return <ListPageSkeleton rows={10} columns={6} avatar />;
}
