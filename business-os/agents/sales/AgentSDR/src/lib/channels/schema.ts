import { jsonb, pgTable, primaryKey, text, timestamp, uuid } from "drizzle-orm/pg-core";
import { organizations } from "@/lib/auth/schema";
import type { Channel } from "./rules";

/**
 * Each organization's sending rules, one row per channel (rules.ts declares
 * them). `values` holds only what the organization changed; everything else
 * resolves to the rule's default, so a missing row means "today's defaults".
 */
export const channelSettings = pgTable(
  "channel_settings",
  {
    organizationId: uuid("organization_id")
      .notNull()
      .references(() => organizations.id),
    channel: text("channel").notNull().$type<Channel>(),
    values: jsonb("values").$type<Record<string, unknown>>().notNull().default({}),
    updatedBy: text("updated_by"),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [primaryKey({ name: "channel_settings_pkey", columns: [table.organizationId, table.channel] })],
);

export type ChannelSettingsRow = typeof channelSettings.$inferSelect;
