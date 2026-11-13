import { redirect } from "next/navigation";

/** This section's overview now lives in Analytics. */
export default function CallingOverviewPage() {
  redirect("/analytics?view=whatsapp");
}
