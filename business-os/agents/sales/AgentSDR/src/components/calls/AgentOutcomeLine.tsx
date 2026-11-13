import * as Badge from "@/components/alignui/badge";
import { AGENT_OUTCOME_LABELS, type AgentOutcome } from "@/lib/calls/contract";

const COLOR = {
  meeting_booked: "green",
  interested: "green",
  human_callback: "green",
  call_back: "blue",
  not_interested: "red",
  wrong_person: "orange",
  do_not_contact: "red",
  no_response: "gray",
  other: "gray",
} as const satisfies Record<AgentOutcome["outcome"], string>;

/** What the AI agent reported with record_outcome: a badge, when, and a one-line summary. */
export function AgentOutcomeLine({ outcome }: { outcome: AgentOutcome }) {
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Badge.Root variant="lighter" size="medium" color={COLOR[outcome.outcome]} className="shrink-0 whitespace-nowrap">
          <Badge.Dot />
          {AGENT_OUTCOME_LABELS[outcome.outcome]}
        </Badge.Root>
        {outcome.when && <span className="text-paragraph-xs text-text-sub-600">{outcome.when}</span>}
      </div>
      {outcome.summary && <p className="text-paragraph-sm text-text-sub-600">{outcome.summary}</p>}
    </div>
  );
}
