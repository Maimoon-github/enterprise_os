/**
 * Client-safe fetch helpers for /api/calling/ai-campaigns (and the per-number
 * AI settings). Throws the route's `{ error }` message. No server imports.
 */

import type {
  AddAiCampaignPeopleResponse,
  AiCampaignDetail,
  AiCampaignLead,
  AiCampaignStats,
  AiLeadDetail,
  AiLeadsQuery,
  CallAiLeadRequest,
  CallAiLeadResponse,
  CreateAiCampaignRequest,
  ListAiCampaignsResponse,
  ListAiLeadsResponse,
  StationAiSettings,
  StationAiSettingsResponse,
  UpdateAiCampaignRequest,
  UpdateAiLeadRequest,
  UpdateStationAiSettingsRequest,
} from "./api";

const BASE = "/api/calling/ai-campaigns";

export async function aiApi<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && typeof init.body === "string" && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(url, { ...init, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data?.error === "string" ? data.error : `Request failed (${response.status})`);
  return data as T;
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export const listAiCampaigns = () => aiApi<ListAiCampaignsResponse>(BASE);
export const createAiCampaign = (request: CreateAiCampaignRequest) => aiApi<AiCampaignDetail>(BASE, json("POST", request));
export const getAiCampaign = (id: string) => aiApi<AiCampaignDetail>(`${BASE}/${id}`);
export const updateAiCampaign = (id: string, request: UpdateAiCampaignRequest) => aiApi<AiCampaignDetail>(`${BASE}/${id}`, json("PATCH", request));
export const archiveAiCampaign = (id: string) => aiApi<{ ok: true }>(`${BASE}/${id}`, json("DELETE"));
export const setAiCampaignStations = (id: string, stationIds: string[]) => aiApi<AiCampaignDetail>(`${BASE}/${id}/stations`, json("PUT", { stationIds }));
export const launchAiCampaign = (id: string) => aiApi<AiCampaignDetail>(`${BASE}/${id}/launch`, json("POST"));
export const getAiCampaignStats = (id: string) => aiApi<AiCampaignStats>(`${BASE}/${id}/stats`);

export function listAiLeads(id: string, query: AiLeadsQuery = {}) {
  const params = new URLSearchParams();
  if (query.status) params.set("status", query.status);
  if (query.q) params.set("q", query.q);
  if (query.page) params.set("page", String(query.page));
  if (query.pageSize) params.set("pageSize", String(query.pageSize));
  return aiApi<ListAiLeadsResponse>(`${BASE}/${id}/leads?${params}`);
}
export const addPeopleToAiCampaign = (id: string, personIds: string[]) => aiApi<AddAiCampaignPeopleResponse>(`${BASE}/${id}/leads`, json("POST", { personIds }));
export const getAiLead = (id: string, contactId: string) => aiApi<AiLeadDetail>(`${BASE}/${id}/leads/${contactId}`);
export const updateAiLead = (id: string, contactId: string, request: UpdateAiLeadRequest) =>
  aiApi<{ lead: AiCampaignLead }>(`${BASE}/${id}/leads/${contactId}`, json("PATCH", request));
/** A call to this lead now (a real WhatsApp call, outside the sequence): the AI agent's, or with `remoteRep` the rep's. */
export const callAiLead = (id: string, contactId: string, request: CallAiLeadRequest = {}) =>
  aiApi<CallAiLeadResponse>(`${BASE}/${id}/leads/${contactId}/call`, json("POST", request));

/** Where the shared People picker and the spreadsheet mapping dialog post to. */
export const aiLeadsEndpoint = (id: string) => `${BASE}/${id}/leads`;
export const aiLeadsUploadEndpoint = (id: string) => `${BASE}/${id}/leads/import`;

export const listStationAiSettings = () => aiApi<StationAiSettingsResponse>("/api/calling/stations/ai-settings");
export const updateStationAiSettings = (stationId: string, request: UpdateStationAiSettingsRequest) =>
  aiApi<{ settings: StationAiSettings }>(`/api/calling/stations/${stationId}/ai-settings`, json("PATCH", request));
