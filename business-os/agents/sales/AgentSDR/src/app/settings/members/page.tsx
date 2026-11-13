import { OrgMembers } from "@/components/settings/organization/OrgMembers";
import { SettingsPage } from "@/components/settings/SettingsPage";

export const metadata = { title: "Members" };
export const dynamic = "force-dynamic";

export default function Page() {
  return (
    <SettingsPage title="Members" description="Invite people and manage what each can do." width="narrow">
      <OrgMembers />
    </SettingsPage>
  );
}
