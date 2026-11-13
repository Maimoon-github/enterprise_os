import { InboxRouteSkeleton } from "@/components/inbox/shell/InboxRouteSkeleton";

/** Matches MessagesLayout while the server page loads, inside the LinkedIn section's padded layout. */
export function MessagesLoadingSkeleton() {
  return <InboxRouteSkeleton inset />;
}
