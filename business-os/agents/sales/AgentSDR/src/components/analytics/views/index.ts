import type { ComponentType } from "react";
import type { AnalyticsView } from "@/lib/analytics/contract";
import { EmailView } from "./EmailView";
import { LinkedinView } from "./LinkedinView";
import { OverviewView } from "./OverviewView";
import { WhatsappView } from "./WhatsappView";
import type { ViewProps } from "./types";

/**
 * The view registry. One entry per view. Each component receives
 * `{ data, loading, onSelectView? }` typed to its own response.
 */
export const views: { [V in AnalyticsView]: ComponentType<ViewProps<V>> } = {
  overview: OverviewView,
  email: EmailView,
  linkedin: LinkedinView,
  whatsapp: WhatsappView,
};

export type { ViewProps } from "./types";
