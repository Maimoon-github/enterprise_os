import { RulesSettingsPage } from "@/components/settings/ChannelSettingsPages";

export const metadata = { title: "Email sending rules" };
export const dynamic = "force-dynamic";

export default function Page() {
  return <RulesSettingsPage channel="email" title="Email sending rules" description="How fast and when mailboxes send. Defaults suit a warm Google Workspace mailbox; change them only if you know your sending reputation." />;
}
