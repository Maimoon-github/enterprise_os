import { RulesSettingsPage } from "@/components/settings/ChannelSettingsPages";

export const metadata = { title: "WhatsApp sending rules" };
export const dynamic = "force-dynamic";

export default function Page() {
  return <RulesSettingsPage channel="whatsapp" title="WhatsApp sending rules" description="How fast numbers may start chats and send. WhatsApp bans numbers that message many strangers quickly." />;
}
