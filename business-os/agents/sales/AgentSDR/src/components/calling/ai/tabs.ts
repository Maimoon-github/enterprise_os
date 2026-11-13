/**
 * The AI campaign page's tabs. A plain module, not the "use client" detail
 * component: the server page reads this list, and a value imported from a
 * client module is only a reference on the server (calling .includes on it
 * threw, and the page failed to load — 27 Oct 2026).
 */
export type AiCampaignTab = "overview" | "leads" | "sequence" | "settings";
export const AI_CAMPAIGN_TABS: readonly AiCampaignTab[] = ["overview", "leads", "sequence", "settings"];

export function isAiCampaignTab(value: unknown): value is AiCampaignTab {
  return typeof value === "string" && (AI_CAMPAIGN_TABS as readonly string[]).includes(value);
}
