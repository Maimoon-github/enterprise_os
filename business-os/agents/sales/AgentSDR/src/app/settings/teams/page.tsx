import { OrgTeams } from "@/components/settings/organization/OrgTeams";
import { SettingsPage } from "@/components/settings/SettingsPage";

export const metadata = { title: "Teams" };
export const dynamic = "force-dynamic";

export default function Page() {
  return (
    <SettingsPage title="Teams" description="Group members into teams." width="narrow">
      <OrgTeams />
    </SettingsPage>
  );
}
