"use client";

import { useRef, useState } from "react";
import {
  RiAddLine,
  RiArrowDownLine,
  RiArrowUpLine,
  RiChat1Line,
  RiDeleteBinLine,
  RiPhoneLine,
  RiTimerLine,
  RiVoiceprintLine,
} from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import * as Input from "@/components/alignui/input";
import * as Select from "@/components/alignui/select";
import * as Textarea from "@/components/alignui/textarea";
import { AgentRehearsal } from "@/components/calls/AgentRehearsal";
import { AgentVoiceRehearsal } from "@/components/calls/AgentVoiceRehearsal";
import {
  AI_CAMPAIGN_MAX_DELAY_HOURS,
  AI_CAMPAIGN_MAX_INSTRUCTIONS_CHARS,
  AI_CAMPAIGN_MAX_MESSAGE_CHARS,
  AI_CAMPAIGN_MAX_STEPS,
  type AiCampaignStep,
} from "@/lib/calls/aiCampaigns/contract";
import { AI_MESSAGE_FIELDS, previewAiMessage, type AiStepStat } from "@/lib/calls/aiCampaigns/api";
import { formatDelay } from "@/components/whatsapp/campaigns/metrics";
import { cn } from "@/utils/cn";

type Unit = "hours" | "days";

export function newAiStep(kind: AiCampaignStep["kind"], delayHours: number): AiCampaignStep {
  const id = `step-${crypto.randomUUID().slice(0, 8)}`;
  return kind === "call" ? { id, kind, delayHours, instructions: "" } : { id, kind, delayHours, body: "" };
}

const unitOf = (hours: number): Unit => (hours > 0 && hours % 24 === 0 ? "days" : "hours");

/**
 * An ordered list of call and WhatsApp-message steps: kind, wait after the
 * previous step, and what the step does. Used twice by the Sequence tab
 * (reach them; chase the booking). Stateless: the parent owns `steps`.
 */
export function AiStepsEditor({
  steps,
  onChange,
  allowEmpty,
  campaignId,
  agentName,
  agentVoice,
  stats,
  statsPhase,
  emptyText,
}: {
  steps: AiCampaignStep[];
  onChange: (steps: AiCampaignStep[]) => void;
  allowEmpty?: boolean;
  /** Needed to rehearse a call step; steps added since the last save are not on the server yet. */
  campaignId: string;
  agentName: string | null;
  agentVoice: string | null;
  stats?: AiStepStat[];
  statsPhase: "reach" | "chase";
  emptyText: string;
}) {
  const [units, setUnits] = useState<Record<string, Unit>>({});
  const [rehearsing, setRehearsing] = useState<{ stepId: string; mode: "voice" | "text" } | null>(null);
  const toggleRehearsal = (stepId: string, mode: "voice" | "text") =>
    setRehearsing(rehearsing?.stepId === stepId && rehearsing.mode === mode ? null : { stepId, mode });
  /** Step ids that existed when the page loaded (so are on the server) — a rehearsal reads the saved step. */
  const [savedIds] = useState(() => new Set(steps.map((step) => step.id)));

  const patch = (id: string, next: Partial<AiCampaignStep>) =>
    onChange(steps.map((step) => (step.id === id ? ({ ...step, ...next } as AiCampaignStep) : step)));

  function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= steps.length) return;
    const next = [...steps];
    [next[index], next[target]] = [next[target]!, next[index]!];
    onChange(next);
  }

  function changeKind(step: AiCampaignStep, kind: AiCampaignStep["kind"]) {
    if (kind === step.kind) return;
    onChange(steps.map((candidate) => (candidate.id === step.id ? { ...newAiStep(kind, step.delayHours), id: step.id } : candidate)));
  }

  function insertToken(step: AiCampaignStep, token: string, input: HTMLTextAreaElement | null) {
    if (step.kind !== "message") return;
    const start = input?.selectionStart ?? step.body.length;
    const end = input?.selectionEnd ?? step.body.length;
    const insert = `{{${token}}}`;
    patch(step.id, { body: `${step.body.slice(0, start)}${insert}${step.body.slice(end)}` });
    requestAnimationFrame(() => {
      input?.focus();
      input?.setSelectionRange(start + insert.length, start + insert.length);
    });
  }

  const statOf = (step: AiCampaignStep) => stats?.find((stat) => stat.phase === statsPhase && stat.stepId === step.id);
  const values: Record<string, string> = {
    ...Object.fromEntries(AI_MESSAGE_FIELDS.map((field) => [field.token, field.sample])),
    agentName: agentName || "Riya",
  };

  return (
    <div>
      {steps.length === 0 && (
        <p className="rounded-xl bg-bg-weak-50 p-4 text-paragraph-sm text-text-sub-600 ring-1 ring-inset ring-stroke-soft-200">{emptyText}</p>
      )}
      <ol className="flex flex-col">
        {steps.map((step, index) => {
          const unit = units[step.id] ?? unitOf(step.delayHours);
          const delayValue = unit === "days" ? step.delayHours / 24 : step.delayHours;
          const stat = statOf(step);
          const Icon = step.kind === "call" ? RiPhoneLine : RiChat1Line;
          return (
            <li key={step.id}>
              {index > 0 && (
                <div className="flex items-center gap-2 py-2 pl-5 text-paragraph-xs text-text-soft-400">
                  <span aria-hidden="true" className="h-4 w-px bg-stroke-soft-200" />
                  <RiTimerLine className="size-3.5" aria-hidden="true" />
                  Wait {formatDelay(step.delayHours)}, if they have not had a real conversation
                </div>
              )}
              <div className="rounded-xl bg-bg-white-0 p-4 shadow-regular-xs ring-1 ring-inset ring-stroke-soft-200">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-bg-weak-50 text-label-xs text-text-sub-600 ring-1 ring-inset ring-stroke-soft-200">{index + 1}</span>
                  <Icon className="size-4 text-text-sub-600" aria-hidden="true" />
                  <Select.Root size="xsmall" value={step.kind} onValueChange={(value) => changeKind(step, value as AiCampaignStep["kind"])}>
                    <Select.Trigger className="w-44" aria-label={`Step ${index + 1} type`}><Select.Value /></Select.Trigger>
                    <Select.Content>
                      <Select.Item value="call">AI call</Select.Item>
                      <Select.Item value="message">WhatsApp message</Select.Item>
                    </Select.Content>
                  </Select.Root>
                  {stat && stat.attempted > 0 && (
                    <span className="text-paragraph-xs tabular-nums text-text-soft-400">
                      {stat.done.toLocaleString("en-US")} done{stat.failed ? ` · ${stat.failed} failed` : ""}
                      {stat.kind === "call" && stat.conversations ? ` · ${stat.conversations} conversations` : ""}
                    </span>
                  )}
                  <div className="ml-auto flex items-center gap-1">
                    <Button.Root variant="neutral" mode="ghost" size="xsmall" onClick={() => move(index, -1)} disabled={index === 0} aria-label="Move step up">
                      <Button.Icon as={RiArrowUpLine} />
                    </Button.Root>
                    <Button.Root variant="neutral" mode="ghost" size="xsmall" onClick={() => move(index, 1)} disabled={index === steps.length - 1} aria-label="Move step down">
                      <Button.Icon as={RiArrowDownLine} />
                    </Button.Root>
                    <Button.Root variant="neutral" mode="ghost" size="xsmall" onClick={() => onChange(steps.filter((candidate) => candidate.id !== step.id))} disabled={!allowEmpty && steps.length <= 1} aria-label="Remove step">
                      <Button.Icon as={RiDeleteBinLine} />
                    </Button.Root>
                  </div>
                </div>

                {index > 0 && (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="text-label-sm text-text-strong-950">Wait</span>
                    <Input.Root size="small" className="w-24">
                      <Input.Wrapper>
                        <Input.Input
                          type="number"
                          min={0}
                          max={unit === "days" ? AI_CAMPAIGN_MAX_DELAY_HOURS / 24 : AI_CAMPAIGN_MAX_DELAY_HOURS}
                          aria-label="Wait before this step"
                          value={Number.isFinite(delayValue) ? String(delayValue) : ""}
                          onChange={(event) => patch(step.id, { delayHours: Math.round(unit === "days" ? Number(event.target.value) * 24 : Number(event.target.value)) })}
                        />
                      </Input.Wrapper>
                    </Input.Root>
                    <Select.Root
                      size="small"
                      value={unit}
                      onValueChange={(value) => {
                        const next = value as Unit;
                        setUnits((current) => ({ ...current, [step.id]: next }));
                        if (next === "days") patch(step.id, { delayHours: Math.max(24, Math.round(step.delayHours / 24) * 24) });
                      }}
                    >
                      <Select.Trigger className="w-28" aria-label="Wait unit"><Select.Value /></Select.Trigger>
                      <Select.Content>
                        <Select.Item value="hours">hours</Select.Item>
                        <Select.Item value="days">days</Select.Item>
                      </Select.Content>
                    </Select.Root>
                    <span className="text-paragraph-sm text-text-sub-600">after the previous step</span>
                  </div>
                )}

                {step.kind === "call" ? (
                  <div className="mt-3">
                    <label className="mb-1.5 block text-label-sm text-text-strong-950" htmlFor={`${step.id}-instructions`}>What is this call for?</label>
                    <Textarea.Root
                      id={`${step.id}-instructions`}
                      simple
                      rows={3}
                      maxLength={AI_CAMPAIGN_MAX_INSTRUCTIONS_CHARS}
                      value={step.instructions}
                      onChange={(event) => patch(step.id, { instructions: event.target.value })}
                      placeholder="On top of the campaign instructions: e.g. “Second try: mention you called yesterday.”"
                    />
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Button.Root
                          variant="neutral"
                          mode="stroke"
                          size="xsmall"
                          onClick={() => toggleRehearsal(step.id, "voice")}
                          aria-expanded={rehearsing?.stepId === step.id && rehearsing.mode === "voice"}
                        >
                          <Button.Icon as={RiPhoneLine} />
                          {rehearsing?.stepId === step.id && rehearsing.mode === "voice" ? "Close rehearsal call" : "Rehearsal call"}
                        </Button.Root>
                        <Button.Root
                          variant="neutral"
                          mode="ghost"
                          size="xsmall"
                          onClick={() => toggleRehearsal(step.id, "text")}
                          aria-expanded={rehearsing?.stepId === step.id && rehearsing.mode === "text"}
                        >
                          <Button.Icon as={RiVoiceprintLine} />
                          {rehearsing?.stepId === step.id && rehearsing.mode === "text" ? "Close" : "Rehearse by typing"}
                        </Button.Root>
                      </div>
                      <span className="text-paragraph-xs tabular-nums text-text-soft-400">{step.instructions.length}/{AI_CAMPAIGN_MAX_INSTRUCTIONS_CHARS}</span>
                    </div>
                    {rehearsing?.stepId === step.id && (
                      <div className="mt-3 rounded-xl bg-bg-weak-50 p-3 ring-1 ring-inset ring-stroke-soft-200">
                        {!savedIds.has(step.id) && (
                          <p className="mb-2 text-paragraph-xs text-warning-dark">This step is new: save the sequence first so the rehearsal uses it.</p>
                        )}
                        <p className="mb-2 text-paragraph-xs text-text-sub-600">
                          {rehearsing.mode === "voice"
                            ? "A call with the agent in your browser, with the campaign's last saved instructions, this step, its voice and goal. Nothing is placed or saved."
                            : "Plays the agent against you in text, with the campaign's last saved instructions and this step. Nothing is placed or saved."}
                        </p>
                        {rehearsing.mode === "voice" ? (
                          <AgentVoiceRehearsal key={step.id} campaignId={campaignId} stepId={step.id} name={agentName ?? undefined} voice={agentVoice ?? undefined} />
                        ) : (
                          <AgentRehearsal campaignId={campaignId} stepId={step.id} name={agentName ?? undefined} voice={agentVoice ?? undefined} />
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <MessageBody step={step} values={values} onBody={(body) => patch(step.id, { body })} onToken={(token, input) => insertToken(step, token, input)} />
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <div className="mt-3">
        <Button.Root
          variant="neutral"
          mode="stroke"
          size="xsmall"
          onClick={() => onChange([...steps, newAiStep(steps.some((step) => step.kind === "call") ? "message" : "call", steps.length === 0 ? 0 : 24)])}
          disabled={steps.length >= AI_CAMPAIGN_MAX_STEPS}
        >
          <Button.Icon as={RiAddLine} />
          {steps.length >= AI_CAMPAIGN_MAX_STEPS ? `Up to ${AI_CAMPAIGN_MAX_STEPS} steps` : "Add step"}
        </Button.Root>
      </div>
    </div>
  );
}

function MessageBody({
  step,
  values,
  onBody,
  onToken,
}: {
  step: Extract<AiCampaignStep, { kind: "message" }>;
  values: Record<string, string>;
  onBody: (body: string) => void;
  onToken: (token: string, input: HTMLTextAreaElement | null) => void;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);
  return (
    <div className="mt-3">
      <label className="mb-1.5 block text-label-sm text-text-strong-950" htmlFor={`${step.id}-body`}>Message</label>
      <div className="mb-2 flex flex-wrap gap-1.5">
        {AI_MESSAGE_FIELDS.map((field) => (
          <button
            type="button"
            key={field.token}
            title={field.label}
            onClick={() => onToken(field.token, ref.current)}
            className="rounded-md bg-bg-weak-50 px-2 py-1 font-mono text-subheading-xs text-text-sub-600 ring-1 ring-inset ring-stroke-soft-200 transition hover:text-text-strong-950 hover:ring-stroke-sub-300"
          >{`{{${field.token}}}`}</button>
        ))}
      </div>
      <Textarea.Root
        id={`${step.id}-body`}
        ref={ref}
        simple
        rows={4}
        maxLength={AI_CAMPAIGN_MAX_MESSAGE_CHARS}
        value={step.body}
        onChange={(event) => onBody(event.target.value)}
        placeholder="Hi {{firstName}}, this is {{agentName}} …"
        hasError={!step.body.trim()}
      />
      <div className="mt-1 flex justify-end text-paragraph-xs tabular-nums text-text-soft-400">{step.body.length}/{AI_CAMPAIGN_MAX_MESSAGE_CHARS}</div>
      <div className="mt-2 rounded-xl bg-bg-weak-50 p-3 ring-1 ring-inset ring-stroke-soft-200">
        <p className="text-label-xs text-text-sub-600">Preview with sample values</p>
        <p className={cn("mt-2 max-w-md whitespace-pre-wrap break-words rounded-xl rounded-tl-sm bg-bg-white-0 px-3.5 py-2.5 text-paragraph-sm leading-6 ring-1 ring-inset ring-stroke-soft-200", step.body.trim() ? "text-text-strong-950" : "text-text-soft-400")}>
          {step.body.trim() ? previewAiMessage(step.body, values) : "Write the message to see it here."}
        </p>
      </div>
    </div>
  );
}
