import "server-only";

import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { channelRules } from "@/lib/channels/rules.server";
import { rulesOf, ruleError, type WeeklyHours } from "@/lib/channels/rules";
import { inOrg } from "@/lib/tenancy/scope";
import type { StationAiSettings, StationAiSettingsResponse, UpdateStationAiSettingsRequest } from "./aiCampaigns/api";
import { CallApiError } from "./sessions";
import { callingStations } from "./schema";

/**
 * A calling number's own limits for AI campaigns: calls a day and calling
 * hours. Blank (null) means the organization's Sending rule. The engine
 * resolves number override → organization rule → default.
 */

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function rule(key: "callsPerDay" | "callingHours") {
  const found = rulesOf("whatsapp").find((candidate) => candidate.key === key);
  if (!found) throw new Error(`The ${key} sending rule is missing`);
  return found;
}

/** Validates a PATCH body; only the keys given move. */
export function parseStationAiSettings(value: unknown): UpdateStationAiSettingsRequest {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new CallApiError(400, "Expected a JSON object");
  const body = value as Record<string, unknown>;
  const unknown = Object.keys(body).find((key) => key !== "callsPerDay" && key !== "callingHours");
  if (unknown) throw new CallApiError(400, `Unknown field: ${unknown}`);
  const request: UpdateStationAiSettingsRequest = {};
  if (body.callsPerDay !== undefined) {
    if (body.callsPerDay === null) request.callsPerDay = null;
    else {
      const problem = ruleError(rule("callsPerDay"), body.callsPerDay);
      if (problem) throw new CallApiError(400, problem);
      request.callsPerDay = body.callsPerDay as number;
    }
  }
  if (body.callingHours !== undefined) {
    if (body.callingHours === null) request.callingHours = null;
    else {
      const problem = ruleError(rule("callingHours"), body.callingHours);
      if (problem) throw new CallApiError(400, problem);
      const hours = body.callingHours as WeeklyHours;
      request.callingHours = {
        timezone: hours.timezone,
        days: [...new Set(hours.days)].sort((a, b) => a - b),
        start: hours.start,
        end: hours.end,
      };
    }
  }
  return request;
}

function toSettings(row: Pick<typeof callingStations.$inferSelect, "id" | "callsPerDay" | "callingHours">): StationAiSettings {
  return { stationId: row.id, callsPerDay: row.callsPerDay, callingHours: row.callingHours };
}

export async function listStationAiSettings(): Promise<StationAiSettingsResponse> {
  const [rows, rules] = await Promise.all([
    db
      .select({ id: callingStations.id, callsPerDay: callingStations.callsPerDay, callingHours: callingStations.callingHours })
      .from(callingStations)
      .where(inOrg(callingStations)),
    channelRules("whatsapp"),
  ]);
  return { settings: rows.map(toSettings), rules: { callsPerDay: rules.callsPerDay, callingHours: rules.callingHours } };
}

export async function updateStationAiSettings(stationId: string, input: UpdateStationAiSettingsRequest): Promise<StationAiSettings> {
  if (!UUID_PATTERN.test(stationId)) throw new CallApiError(404, "Calling number not found");
  const updates: Partial<typeof callingStations.$inferInsert> = { updatedAt: new Date() };
  if (input.callsPerDay !== undefined) updates.callsPerDay = input.callsPerDay;
  if (input.callingHours !== undefined) updates.callingHours = input.callingHours;
  const [row] = await db
    .update(callingStations)
    .set(updates)
    .where(and(inOrg(callingStations), eq(callingStations.id, stationId)))
    .returning({ id: callingStations.id, callsPerDay: callingStations.callsPerDay, callingHours: callingStations.callingHours });
  if (!row) throw new CallApiError(404, "Calling number not found");
  return toSettings(row);
}
