import { RulesSettingsPage } from "@/components/settings/ChannelSettingsPages";

export const metadata = { title: "LinkedIn sending rules" };
export const dynamic = "force-dynamic";

export default function Page() {
  return <RulesSettingsPage channel="linkedin" title="LinkedIn sending rules" description="How many invitations and messages each account sends, how fast, and when. LinkedIn restricts accounts that move too fast, so the defaults are conservative." />;
}
