import { redirect } from "next/navigation";

/**
 * Leads is the single cross-channel lead directory. Keep this redirect so
 * existing bookmarks to the retired LinkedIn-only directory remain useful.
 */
export default function LeadsPage() {
  redirect("/leads");
}
