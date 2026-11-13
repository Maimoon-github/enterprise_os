import { RecordPageSkeleton } from "@/components/crm/CrmSkeletons";

/**
 * Shown the instant a record link is followed, before the route's server
 * render arrives. Without it the click has no visible effect until the whole
 * page is ready, which reads as the app hanging.
 */
export default function CrmRecordLoading() {
  return <RecordPageSkeleton />;
}
