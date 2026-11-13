import { RequiresPlatform } from "@/components/settings/RequiresPlatform";

/**
 * The Email section (campaigns, the Master Inbox and its notes and tasks)
 * runs on Google Workspace, so all of it waits behind that connection, the way
 * /linkedin waits on Unipile. Each page supplies its own padding, so only the
 * Connect prompt gets it here.
 */

// Reads the database (is Google Workspace connected?), so the segment renders per request.
export const dynamic = "force-dynamic";

export default function OutreachLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequiresPlatform platform="google" className="h-full overflow-auto bg-bg-white-0 px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
      {children}
    </RequiresPlatform>
  );
}
