import { redirect } from "next/navigation";

/** This section's overview now lives in Analytics. */
export default function CrmOverviewPage() {
  redirect("/analytics");
}
