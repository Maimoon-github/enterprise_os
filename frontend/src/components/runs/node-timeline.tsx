import { RunStreamEvent } from "@/types/graph";

interface NodeTimelineProps {
  events: RunStreamEvent[];
}

export function NodeTimeline({ events }: NodeTimelineProps) {
  if (events.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-bloodstone-text-muted glass-panel rounded-xl">
        Awaiting graph execution events...
      </div>
    );
  }

  const getBadgeStyle = (event: RunStreamEvent) => {
    if (event.event === "interrupt") {
      return "bg-glass-crimson text-bloodstone-text border-bloodstone-crimson shadow-crimson-glow";
    }
    if (event.event === "node_finish" || (event.event === "complete" && event.data.status === "completed")) {
      return "bg-glass-emerald text-bloodstone-mint border-glass-specular";
    }
    if (event.event === "tool_call") {
      return "bg-glass-base text-bloodstone-mint border-bloodstone-mint/40";
    }
    return "bg-glass-base text-bloodstone-text border-glass-subtle";
  };

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto scrollbar-thin">
      {events.map((ev, i) => {
        const badgeClass = getBadgeStyle(ev);
        return (
          <div
            key={i}
            className="text-xs p-3 glass-panel rounded-lg flex items-center justify-between font-mono"
          >
            <div className="flex items-center gap-3">
              <span className={`px-2 py-0.5 rounded border text-[11px] ${badgeClass}`}>
                {ev.event}
              </span>
              <span className="text-bloodstone-text">
                {ev.data.node || ev.data.tool || ev.data.status || "super-step"}
              </span>
            </div>
            <div className="text-bloodstone-text-dim text-[11px]">
              {ev.data.step ? `Step ${ev.data.step}` : ""}
              {ev.data.status ? ` • ${ev.data.status}` : ""}
            </div>
          </div>
        );
      })}
    </div>
  );
}
