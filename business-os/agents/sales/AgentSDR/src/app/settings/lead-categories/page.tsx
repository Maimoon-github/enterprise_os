import { SettingsPage } from "@/components/settings/SettingsPage";
import CrmSettingsClient from "@/components/crm/CrmSettingsClient";

export const metadata = { title: "Lead categories" };
export const dynamic = "force-dynamic";

export default function LeadCategoriesPage() {
  return (
    <SettingsPage
      title="Lead categories"
      description="The subcategories the AI sorts replies into, and the reply sequence each one starts."
    >
      <CrmSettingsClient />
    </SettingsPage>
  );
}
