"use client";

import { useRef, useState } from "react";
import { RiLoader4Line, RiRestartLine, RiSendPlaneLine } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import * as Input from "@/components/alignui/input";
import { errorMessage } from "@/components/crm/crm-utils";
import { AGENT_OUTCOME_LABELS } from "@/lib/calls/contract";

type Turn = { role: "lead" | "agent"; text: string };
export type Tool = { name: string; args: Record<string, unknown> };
type Line = Turn & { tools?: Tool[] };

const MAX_TURNS = 40;

/** A tool call as a short chip: "record_outcome: meeting_booked — Thursday around 4 pm". */
export function toolLabel(tool: Tool): string {
  const text = (key: string) => (typeof tool.args[key] === "string" ? (tool.args[key] as string) : "");
  if (tool.name === "record_outcome") {
    const outcome = text("outcome");
    const when = text("when") || text("whenAt");
    const label = outcome in AGENT_OUTCOME_LABELS ? outcome : outcome || "?";
    return `record_outcome: ${label}${when ? ` — ${when}` : ""}`;
  }
  const reason = text("reason");
  return `${tool.name}${reason ? `: ${reason}` : ""}`;
}

/**
 * Rehearse the AI agent: type as the lead and read what the agent says, with
 * the exact prompt a campaign call gets (POST /api/calling/agent/rehearse).
 * The conversation lives here; nothing is saved and no call is placed.
 */
export function AgentRehearsal({ campaignId, contactId, stepId, brief, name, voice }: {
  campaignId?: string;
  /** Rehearse as this lead of the campaign: their name, company, history and own instructions. */
  contactId?: string;
  stepId?: string;
  brief?: string;
  name?: string;
  voice?: string;
}) {
  const [lines, setLines] = useState<Line[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const started = lines.length > 0;

  async function ask(turns: Turn[], base: Line[]) {
    const id = ++requestId.current;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/calling/agent/rehearse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ campaignId, contactId, stepId, brief, name, voice, turns }),
      });
      const body = (await response.json().catch(() => null)) as { reply?: string; tools?: Tool[]; error?: string } | null;
      if (!response.ok || !body) throw new Error(body?.error ?? `The rehearsal failed (HTTP ${response.status})`);
      if (id !== requestId.current) return;
      setLines([...base, { role: "agent", text: body.reply ?? "", tools: body.tools ?? [] }]);
    } catch (caught) {
      if (id === requestId.current) setError(errorMessage(caught));
    } finally {
      if (id === requestId.current) setBusy(false);
    }
  }

  function start() {
    void ask([], []);
  }

  function restart() {
    requestId.current += 1;
    setLines([]);
    setDraft("");
    setError(null);
    setBusy(false);
  }

  function send() {
    const text = draft.trim();
    if (!text || busy || lines.length >= MAX_TURNS) return;
    const next: Line[] = [...lines, { role: "lead", text }];
    setLines(next);
    setDraft("");
    void ask(next.map(({ role, text: said }) => ({ role, text: said })).filter((turn) => turn.text), next);
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-stroke-soft-200 bg-bg-white-0 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-paragraph-xs text-text-sub-600">Type as the lead to see what the agent says. No call is placed.</p>
        {started ? (
          <Button.Root variant="neutral" mode="stroke" size="xxsmall" onClick={restart}>
            <Button.Icon as={RiRestartLine} />
            Restart
          </Button.Root>
        ) : null}
      </div>

      {!started ? (
        <div>
          <Button.Root variant="neutral" mode="stroke" size="xxsmall" onClick={start} disabled={busy}>
            {busy ? <Button.Icon as={RiLoader4Line} className="animate-spin" /> : null}
            Start
          </Button.Root>
        </div>
      ) : (
        <div className="flex max-h-80 flex-col gap-2 overflow-y-auto">
          {lines.map((line, index) => (
            <div key={index} className={line.role === "lead" ? "flex flex-col items-end gap-1" : "flex flex-col items-start gap-1"}>
              <div
                className={
                  line.role === "lead"
                    ? "max-w-[85%] rounded-xl bg-bg-weak-50 px-3 py-2 text-paragraph-sm text-text-strong-950"
                    : "max-w-[85%] rounded-xl bg-information-lighter px-3 py-2 text-paragraph-sm text-text-strong-950"
                }
              >
                {line.text || <span className="text-text-soft-400">(said nothing)</span>}
              </div>
              {line.tools?.map((tool, toolIndex) => (
                <span key={toolIndex} className="rounded-md bg-bg-weak-50 px-2 py-0.5 text-subheading-2xs text-text-sub-600">
                  {toolLabel(tool)}
                </span>
              ))}
            </div>
          ))}
          {busy ? <RiLoader4Line className="size-4 animate-spin text-text-soft-400" aria-label="The agent is replying" /> : null}
        </div>
      )}

      {error ? <p className="text-paragraph-xs text-error-base">{error}</p> : null}

      {started ? (
        <form
          className="flex items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            send();
          }}
        >
          <Input.Root size="small" className="flex-1">
            <Input.Wrapper>
              <Input.Input
                value={draft}
                maxLength={1000}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="What the lead says…"
                disabled={busy || lines.length >= MAX_TURNS}
              />
            </Input.Wrapper>
          </Input.Root>
          <Button.Root type="submit" variant="neutral" size="xsmall" disabled={busy || !draft.trim() || lines.length >= MAX_TURNS}>
            <Button.Icon as={RiSendPlaneLine} />
            Send
          </Button.Root>
        </form>
      ) : null}
    </div>
  );
}

