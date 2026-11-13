import { ConnectionSettingsPage } from "@/components/settings/ChannelSettingsPages";

export const metadata = { title: "Email connection" };
export const dynamic = "force-dynamic";

export default function Page() {
  return (
    <ConnectionSettingsPage
      platforms={[{ platform: "google" }]}
      comingSoon={[
        {
          name: "Microsoft Outlook",
          description: "Send and read email from Microsoft 365 and Outlook mailboxes, connected through Microsoft Azure.",
          iconUrl: "/Integrations - Icon/microsoft.svg",
          enables: ["Outlook mailboxes", "email campaigns", "inbox sync"],
        },
      ]}
      title="Email connection"
      description="The Google Workspace service account that sends and reads Gmail for every mailbox in Email → Accounts. Microsoft Outlook is coming soon."
    />
  );
}
