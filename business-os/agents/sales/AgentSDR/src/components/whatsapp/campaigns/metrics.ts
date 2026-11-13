import type * as Badge from "@/components/alignui/badge";
import type {
  WhatsappCampaignLeadStatus,
  WhatsappCampaignStats,
  WhatsappCampaignStatus,
} from "@/lib/whatsapp/campaigns/contract";

type BadgeColor = React.ComponentProps<typeof Badge.Root>["color"];

export const CAMPAIGN_STATUS: Record<WhatsappCampaignStatus, { label: string; color: BadgeColor }> = {
  active: { label: "Active", color: "green" },
  paused: { label: "Paused", color: "orange" },
};

/** Every lead status, in sequence order, with its label and badge colour. */
export const LEAD_STATUS: Record<WhatsappCampaignLeadStatus, { label: string; color: BadgeColor }> = {
  queued: { label: "Queued", color: "gray" },
  in_sequence: { label: "In sequence", color: "blue" },
  completed: { label: "Completed", color: "purple" },
  replied: { label: "Replied", color: "green" },
  stopped: { label: "Stopped", color: "orange" },
  failed: { label: "Failed", color: "red" },
};

/**
 * What a campaign's lead-status counts add up to. A lead's status is where
 * it is now, so "messaged" is every lead past the queue that received a
 * message: in sequence, completed or replied. Stopped and failed leads may
 * or may not have been messaged first, so they are not counted as messaged.
 * Reply rate is replied / messaged.
 */
export type CampaignFunnel = {
  total: number;
  queued: number;
  inSequence: number;
  completed: number;
  replied: number;
  stopped: number;
  failed: number;
  messaged: number;
  messagesSent: number;
  replyRate: number | null;
  /** 0-1 share of leads that have left the queue; null with no leads. */
  progress: number | null;
};

export function campaignFunnel(s: WhatsappCampaignStats): CampaignFunnel {
  const messaged = s.in_sequence + s.completed + s.replied;
  return {
    total: s.total,
    queued: s.queued,
    inSequence: s.in_sequence,
    completed: s.completed,
    replied: s.replied,
    stopped: s.stopped,
    failed: s.failed,
    messaged,
    messagesSent: s.messagesSent,
    replyRate: messaged > 0 ? s.replied / messaged : null,
    progress: s.total > 0 ? Math.min((s.total - s.queued) / s.total, 1) : null,
  };
}

/** Why a campaign cannot launch yet, or null. Mirrors the API's own checks. */
export function launchBlocker(input: { connectedSenders: number; leads: number; firstMessage: string | undefined }): string | null {
  if (input.connectedSenders === 0) return "Choose at least one connected WhatsApp number";
  if (input.leads === 0) return "Add at least one lead";
  if (!input.firstMessage?.trim()) return "Write the first message";
  return null;
}

export function formatDelay(hours: number): string {
  if (hours % 24 === 0) {
    const days = hours / 24;
    return `${days} ${days === 1 ? "day" : "days"}`;
  }
  return `${hours} ${hours === 1 ? "hour" : "hours"}`;
}

/** "5m ago" / "in 3h", for a timestamp either side of now. */
export function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const diffMinutes = Math.round((date.getTime() - Date.now()) / 60000);
  const abs = Math.abs(diffMinutes);
  const past = diffMinutes < 0;
  let text: string;
  if (abs < 1) return "just now";
  if (abs < 60) text = `${abs}m`;
  else if (abs < 60 * 24) text = `${Math.round(abs / 60)}h`;
  else if (abs < 60 * 24 * 30) text = `${Math.round(abs / (60 * 24))}d`;
  else return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return past ? `${text} ago` : `in ${text}`;
}
