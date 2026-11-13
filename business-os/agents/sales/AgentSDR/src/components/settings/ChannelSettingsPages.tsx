import type { ReactNode } from "react";
import { ChannelRulesForm } from "@/components/settings/ChannelRulesForm";
import { ComingSoonCard, PlatformConnection, type ComingSoonConnection } from "@/components/settings/PlatformConnection";
import { SettingsPage } from "@/components/settings/SettingsPage";
import { can, requirePageOrgContext } from "@/lib/auth/context";
import type { Channel } from "@/lib/channels/rules";
import { channelRulesForSettings } from "@/lib/channels/rules.server";
import type { PlatformKey } from "@/lib/platform/catalog";
import { listPlatformStatus } from "@/lib/platform/credentials";
import { runInOrganization } from "@/lib/tenancy/scope";
import { calcomWebhookUrl } from "@/lib/calls/aiCampaigns/booking";

/** The URL a platform's own webhook settings take, for the platforms that need one pasted. */
function platformWebhookUrl(platform: PlatformKey, organizationId: string): string | null | undefined {
  if (platform === "calcom") return calcomWebhookUrl(organizationId);
  return undefined;
}

/**
 * The two kinds of page every channel section in Settings has besides its
 * accounts list: Connection (the platform integrations it runs on, one card
 * each) and Sending rules (src/lib/channels/rules.ts). Each route under /settings is a
 * one-line use of these, plus its @modal/(.)settings twin.
 */

export async function ConnectionSettingsPage({
  platforms,
  comingSoon = [],
  title,
  description,
  children,
}: {
  /** `webhookUrl`: show the organization's webhook URL for this platform (Cal.com). */
  platforms: { platform: PlatformKey; note?: string; webhookUrl?: boolean }[];
  /** Connections planned for this channel, shown after the real ones. */
  comingSoon?: ComingSoonConnection[];
  title: string;
  description: string;
  /** Anything else the channel runs on, after its integrations. */
  children?: ReactNode;
}) {
  const ctx = await requirePageOrgContext();
  const statuses = await runInOrganization(ctx.organizationId, () => listPlatformStatus());
  return (
    <SettingsPage title={title} description={description} width="narrow">
      <div className="flex flex-col gap-6">
        {platforms.map(({ platform, note, webhookUrl }) => (
          <PlatformConnection
            key={platform}
            platformKey={platform}
            status={statuses.find((s) => s.key === platform) ?? null}
            note={note}
            webhookUrl={webhookUrl ? platformWebhookUrl(platform, ctx.organizationId) : undefined}
          />
        ))}
        {comingSoon.map((connection) => (
          <ComingSoonCard key={connection.name} connection={connection} />
        ))}
        {children}
      </div>
    </SettingsPage>
  );
}

export async function RulesSettingsPage({ channel, title, description }: { channel: Channel; title: string; description: string }) {
  const ctx = await requirePageOrgContext();
  const { values } = await runInOrganization(ctx.organizationId, () => channelRulesForSettings(channel));
  return (
    <SettingsPage title={title} description={description} width="narrow">
      <ChannelRulesForm channel={channel} initialValues={values} canEdit={can(ctx, { integrations: ["manage"] })} />
    </SettingsPage>
  );
}
