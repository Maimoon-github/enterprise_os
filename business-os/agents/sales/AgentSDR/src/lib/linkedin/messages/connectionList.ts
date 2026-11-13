/**
 * Filters, constants and row mapping for the messages list.
 *
 * The two database-backed readers live in ./connectionList.server — client
 * components import the constants and `ConnectionItem` from here, and a
 * module-level `db` import would pull the postgres driver into the browser
 * bundle and fail the build.
 */
import type { LeadStatus } from "@/lib/linkedin/schema";
import { parsePageParam, PAGE_SIZE } from "@/lib/linkedin/pagination";
import type { InboxCrmSummary } from "./crmContext";

export type ConnectionItem = {
  id: string;
  name: string | null;
  headline: string | null;
  profilePictureUrl: string | null;
  linkedinUrl: string | null;
  providerId: string;
  chatId: string | null;
  connectedAt: string | null;
  leadStatus: string | null;
  campaignId: string | null;
  campaignName: string | null;
  linkedInAccountId: string | null;
  linkedInAccountUsername: string | null;
  linkedInAccountName: string | null;
  linkedInAccountPicture: string | null;
  lastMessage: { text: string; type: string; createdAt: string } | null;
  unseenCount: number;
  /** CRM state for connections whose thread is a CRM conversation; null otherwise. */
  crm: InboxCrmSummary | null;
};

/** Default messages list: campaign leads only (any status). */
export const ALL_LEADS_FILTER = "all_leads";

/** Default messages status filter — show replied leads first. */
export const DEFAULT_MESSAGES_STATUS_FILTER: LeadStatus = "REPLIED";

/** LinkedIn connections with no linked campaign lead. */
export const CONNECTIONS_ONLY_FILTER = "connections_only";

/** Conversations whose latest canonical message came from the prospect. */
export const UNREPLIED_FILTER = "unreplied";

export const isAllLeadsFilter = (status?: string) =>
  !status || status === ALL_LEADS_FILTER;

export type ConnectionListFilters = {
  search?: string;
  campaignId?: string;
  accountId?: string;
  status?: string;
  periodDays?: number | null;
  /** CRM classification filters; a connection matches through its CRM record. */
  categoryKey?: string;
  subcategoryId?: string;
};

/**
 * Row shape produced by the connection list query: the Connection columns plus
 * the two joined account records, the joined lead/campaign fields, and the two
 * per-connection message aggregates (latest message, unseen count).
 */
export type ConnectionRow = {
  id: string;
  name: string | null;
  headline: string | null;
  profilePictureUrl: string | null;
  linkedinUrl: string | null;
  providerId: string;
  chatId: string | null;
  connectedAt: Date | null;
  linkedInAccount: {
    id: string;
    username: string;
    name: string | null;
    profilePictureUrl: string | null;
  } | null;
  lead: {
    status: string;
    campaign: { id: string; name: string } | null;
    linkedInAccount: {
      id: string;
      username: string;
      name: string | null;
      profilePictureUrl: string | null;
    } | null;
  } | null;
  messages: { text: string; type: string; createdAt: Date }[];
  _count: { messages: number };
};

export const mapConnectionToItem = (c: ConnectionRow): ConnectionItem => ({
  id: c.id,
  name: c.name ?? null,
  headline: c.headline ?? null,
  profilePictureUrl: c.profilePictureUrl ?? null,
  linkedinUrl: c.linkedinUrl ?? null,
  providerId: c.providerId,
  chatId: c.chatId,
  connectedAt: c.connectedAt?.toISOString() ?? null,
  leadStatus: c.lead?.status ?? null,
  campaignId: c.lead?.campaign?.id ?? null,
  campaignName: c.lead?.campaign?.name ?? null,
  linkedInAccountId: c.linkedInAccount?.id ?? c.lead?.linkedInAccount?.id ?? null,
  linkedInAccountUsername: c.linkedInAccount?.username ?? c.lead?.linkedInAccount?.username ?? null,
  linkedInAccountName: c.linkedInAccount?.name ?? c.lead?.linkedInAccount?.name ?? null,
  linkedInAccountPicture:
    c.linkedInAccount?.profilePictureUrl ?? c.lead?.linkedInAccount?.profilePictureUrl ?? null,
  lastMessage: c.messages[0]
    ? {
        text: c.messages[0].text,
        type: c.messages[0].type,
        createdAt: c.messages[0].createdAt.toISOString(),
      }
    : null,
  unseenCount: c._count.messages,
  crm: null,
});

export const connectionPageSize = PAGE_SIZE;

export const parseConnectionListFilters = (searchParams: URLSearchParams): ConnectionListFilters => {
  const periodDaysRaw = searchParams.get("periodDays");
  return {
    search: searchParams.get("search") ?? undefined,
    campaignId: searchParams.get("campaignId") ?? undefined,
    accountId: searchParams.get("accountId") ?? undefined,
    status: searchParams.get("status") ?? undefined,
    periodDays:
      periodDaysRaw && Number.isFinite(Number(periodDaysRaw)) ? Number(periodDaysRaw) : null,
    categoryKey: searchParams.get("categoryKey") ?? undefined,
    subcategoryId: searchParams.get("subcategoryId") ?? undefined,
  };
};

export const parseConnectionListPage = (searchParams: URLSearchParams) =>
  parsePageParam(searchParams.get("page") ?? undefined);

/** Unread inbound messages on connections linked to leads with REPLIED status. */
