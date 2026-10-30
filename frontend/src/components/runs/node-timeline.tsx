import { RunStreamEvent } from "@/types/graph";

interface NodeTimelineProps {
  events: RunStreamEvent[];
}

export function NodeTimeline({ events }: NodeTimelineProps) {
  if (events.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-slate-500 bg-slate-900 border border-slate-800 rounded-xl">
        Awaiting graph execution events...
      </div>
    );
  }

  const getBadgeStyle = (event: RunStreamEvent) => {
    if (event.event === "interrupt") {
      return "bg-amber-950/60 text-amber-300 border-amber-800";
    }
    if (event.event === "node_finish" || (event.event === "complete" && event.data.status === "completed")) {
      return "bg-emerald-950/60 text-emerald-300 border-emerald-800";
    }
    if (event.event === "tool_call") {
      return "bg-purple-950/60 text-purple-300 border-purple-800";
    }
    return "bg-indigo-950/60 text-indigo-300 border-indigo-800";
  };

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto scrollbar-thin">
      {events.map((ev, i) => {
        const badgeClass = getBadgeStyle(ev);
        return (
          <div
            key={i}
            className="text-xs p-3 bg-slate-900 border border-slate-800/80 rounded-lg flex items-center justify-between font-mono"
          >
            <div className="flex items-center gap-3">
              <span className={`px-2 py-0.5 rounded border text-[11px] ${badgeClass}`}>
                {ev.event}
              </span>
              <span className="text-slate-200">
                {ev.data.node || ev.data.tool || ev.data.status || "super-step"}
              </span>
            </div>
            <div className="text-slate-500 text-[11px]">
              {ev.data.step ? `Step ${ev.data.step}` : ""}
              {ev.data.status ? ` • ${ev.data.status}` : ""}
            </div>
          </div>
        );
      })}
    </div>
  );
}
