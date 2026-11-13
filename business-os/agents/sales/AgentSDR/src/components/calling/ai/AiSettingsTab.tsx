"use client";

import { useEffect, useMemo, useState } from "react";
import { RiArchiveLine, RiErrorWarningLine, RiLoader4Line, RiPauseCircleLine, RiPlayCircleLine, RiSaveLine } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import { VoicePreviewButton } from "@/components/calls/VoicePreviewButton";
import { KnowledgePicker } from "./KnowledgePicker";
import * as Select from "@/components/alignui/select";
import * as Textarea from "@/components/alignui/textarea";
import { Frame, FrameFooter, FrameHeader, FramePanel } from "@/components/analytics/kit/Frame";
import { TextField } from "@/components/calls/fields";
import { AGENT_VOICES, DEFAULT_AGENT_NAME, DEFAULT_AGENT_VOICE, MAX_AGENT_NAME_CHARS } from "@/lib/calls/contract";
import {
  AI_CAMPAIGN_MAX_BOOKING_MESSAGE,
  AI_CAMPAIGN_MAX_INSTRUCTIONS,
  aiSettingsError,
  type AiCampaignDetail,
  type UpdateAiCampaignRequest,
} from "@/lib/calls/aiCampaigns/api";
import { AI_CAMPAIGN_GOALS, AI_CAMPAIGN_GOAL_LABELS, AI_CAMPAIGN_MAX_CALLBACKS, type AiCampaignGoal } from "@/lib/calls/aiCampaigns/contract";
import { listCallingStations } from "@/lib/calls/client";
import { setAiCampaignStations, updateAiCampaign } from "@/lib/calls/aiCampaigns/client";
import type { CallingStation } from "@/lib/calls/stationContract";
import { cn } from "@/utils/cn";
import { errorText, NumberPicker, useBeforeUnload } from "./aiShared";

const DEFAULT_VOICE = "default";

type Draft = {
  goal: AiCampaignGoal;
  instructions: string;
  agentName: string;
  agentVoice: string;
  bookingUrl: string;
  bookingMessage: string;
  maxCallbacks: number;
  knowledgeIds: string[] | null;
};

const draftOf = (campaign: AiCampaignDetail): Draft => ({
  goal: campaign.goal,
  instructions: campaign.instructions,
  agentName: campaign.agentName ?? "",
  agentVoice: campaign.agentVoice ?? DEFAULT_VOICE,
  bookingUrl: campaign.bookingUrl ?? "",
  bookingMessage: campaign.bookingMessage,
  maxCallbacks: campaign.maxCallbacks,
  knowledgeIds: campaign.knowledgeIds,
});

/** The Settings tab: what the calls are for, the agent, booking, call-backs, numbers, and pause / archive. */
export function AiSettingsTab({
  campaign,
  onSaved,
  onToggle,
  onArchive,
  toggling,
}: {
  campaign: AiCampaignDetail;
  onSaved: () => void;
  onToggle: () => void;
  onArchive: () => void;
  toggling: boolean;
}) {
  const [draft, setDraft] = useState<Draft>(() => draftOf(campaign));
  const [saved, setSaved] = useState<Draft>(() => draftOf(campaign));
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [stations, setStations] = useState<CallingStation[] | null>(null);
  const [stationsError, setStationsError] = useState<string | null>(null);
  const savedNumberIds = useMemo(() => campaign.numbers.map((number) => number.id), [campaign.numbers]);
  const [numberIds, setNumberIds] = useState<string[]>(savedNumberIds);
  const [savingNumbers, setSavingNumbers] = useState(false);
  const [numbersError, setNumbersError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listCallingStations()
      .then((response) => { if (!cancelled) setStations(response.stations); })
      .catch((cause) => { if (!cancelled) setStationsError(errorText(cause, "Could not load numbers")); });
    return () => { cancelled = true; };
  }, []);

  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  const numbersDirty = [...numberIds].sort().join() !== [...savedNumberIds].sort().join();
  useBeforeUnload(dirty || numbersDirty);

  const handover = draft.goal === "human_callback";
  const problem = aiSettingsError({
    goal: draft.goal,
    instructions: draft.instructions,
    bookingUrl: handover ? null : draft.bookingUrl.trim() || null,
    bookingMessage: draft.bookingMessage,
    maxCallbacks: draft.maxCallbacks,
  });
  const nameTooLong = draft.agentName.trim().length > MAX_AGENT_NAME_CHARS;

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setJustSaved(false);
    setError(null);
    setDraft((current) => ({ ...current, [key]: value }));
  };

  async function save() {
    if (problem) { setError(problem); return; }
    setSaving(true);
    setError(null);
    try {
      const request: UpdateAiCampaignRequest = {
        goal: draft.goal,
        instructions: draft.instructions,
        agentName: draft.agentName.trim() || null,
        agentVoice: draft.agentVoice === DEFAULT_VOICE ? null : draft.agentVoice,
        bookingUrl: handover ? null : draft.bookingUrl.trim() || null,
        bookingMessage: draft.bookingMessage,
        maxCallbacks: draft.maxCallbacks,
        knowledgeIds: draft.knowledgeIds,
      };
      const updated = await updateAiCampaign(campaign.id, request);
      const next = draftOf(updated);
      setDraft(next);
      setSaved(next);
      setJustSaved(true);
      onSaved();
    } catch (cause) {
      setError(errorText(cause, "Could not save the settings"));
    } finally {
      setSaving(false);
    }
  }

  async function saveNumbers() {
    setSavingNumbers(true);
    setNumbersError(null);
    try {
      await setAiCampaignStations(campaign.id, numberIds);
      onSaved();
    } catch (cause) {
      setNumbersError(errorText(cause, "Could not save the numbers"));
    } finally {
      setSavingNumbers(false);
    }
  }

  const launched = campaign.state !== "draft";

  return (
    <div className="space-y-4">
      <Frame>
        <FrameHeader title="What the calls are for" description="The goal decides what the agent agrees to when a lead is interested." />
        <FramePanel>
          <div role="radiogroup" aria-label="Goal" className="grid gap-2 sm:grid-cols-3">
            {AI_CAMPAIGN_GOALS.map((goal) => {
              const active = draft.goal === goal;
              return (
                <button
                  key={goal}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => set("goal", goal)}
                  className={cn(
                    "rounded-xl p-3.5 text-left outline-none ring-1 ring-inset transition focus-visible:ring-2 focus-visible:ring-primary-base",
                    active ? "bg-bg-weak-50 ring-primary-base" : "ring-stroke-soft-200 hover:bg-bg-weak-50",
                  )}
                >
                  <span className="block text-label-sm text-text-strong-950">{AI_CAMPAIGN_GOAL_LABELS[goal].label}</span>
                  <span className="mt-1 block text-paragraph-xs text-text-sub-600">{AI_CAMPAIGN_GOAL_LABELS[goal].help}</span>
                </button>
              );
            })}
          </div>

          <div className="mt-5">
            <label className="mb-1.5 block text-label-sm text-text-strong-950">Knowledge</label>
            <KnowledgePicker value={draft.knowledgeIds} onChange={(ids) => set("knowledgeIds", ids)} />
          </div>

          <div className="mt-5">
            <label htmlFor="ai-instructions" className="mb-1.5 block text-label-sm text-text-strong-950">Campaign instructions</label>
            <p className="mb-2 text-paragraph-xs text-text-sub-600">
              What every call in this campaign is about, on top of the Knowledge above: who you are calling, what you offer them, what to find out. Each call step can add its own instructions on top.
            </p>
            <Textarea.Root
              id="ai-instructions"
              simple
              rows={8}
              maxLength={AI_CAMPAIGN_MAX_INSTRUCTIONS}
              value={draft.instructions}
              onChange={(event) => set("instructions", event.target.value)}
              placeholder="You are calling founders of D2C brands who run Meta ads. We help them … Find out whether they spend more than ₹5 lakh a month on ads …"
            />
            <div className="mt-1 flex justify-end text-paragraph-xs tabular-nums text-text-soft-400">{draft.instructions.length}/{AI_CAMPAIGN_MAX_INSTRUCTIONS}</div>
          </div>
        </FramePanel>
      </Frame>

      <Frame>
        <FrameHeader title="The agent" description="How the agent introduces itself. Every call in this campaign uses the same name and voice, so a lead hears one person." />
        <FramePanel>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Agent name"
              value={draft.agentName}
              onChange={(value) => set("agentName", value)}
              placeholder={DEFAULT_AGENT_NAME}
              maxLength={MAX_AGENT_NAME_CHARS + 10}
              aria-invalid={nameTooLong || undefined}
            />
            <div>
              <label className="mb-1.5 block text-label-sm text-text-strong-950">Voice</label>
              <div className="flex items-center gap-2">
                <div className="min-w-0 flex-1">
                  <Select.Root size="small" value={draft.agentVoice} onValueChange={(value) => set("agentVoice", value)}>
                    <Select.Trigger aria-label="Voice"><Select.Value /></Select.Trigger>
                    <Select.Content>
                      <Select.Item value={DEFAULT_VOICE}>Default ({DEFAULT_AGENT_VOICE})</Select.Item>
                      {AGENT_VOICES.map((voice) => <Select.Item key={voice.id} value={voice.id}>{voice.label}</Select.Item>)}
                    </Select.Content>
                  </Select.Root>
                </div>
                <VoicePreviewButton voice={draft.agentVoice} name={draft.agentName} />
              </div>
            </div>
          </div>
        </FramePanel>
      </Frame>

      {!handover && (
        <Frame>
          <FrameHeader title="Booking" description="Where interested leads book a time with your team (a Cal.com page), and the WhatsApp that sends them there right after the call." />
          <FramePanel className="space-y-4">
            <TextField label="Booking link" value={draft.bookingUrl} onChange={(value) => set("bookingUrl", value)} placeholder="https://cal.com/acme/30min" inputMode="url" />
            <div>
              <label htmlFor="ai-booking-message" className="mb-1.5 block text-label-sm text-text-strong-950">Booking message</label>
              <Textarea.Root
                id="ai-booking-message"
                simple
                rows={4}
                maxLength={AI_CAMPAIGN_MAX_BOOKING_MESSAGE}
                value={draft.bookingMessage}
                onChange={(event) => set("bookingMessage", event.target.value)}
                hasError={Boolean(draft.bookingUrl.trim()) && !draft.bookingMessage.includes("{{bookingLink}}")}
              />
              <p className="mt-1 text-paragraph-xs text-text-sub-600">Must include <code className="font-mono">{"{{bookingLink}}"}</code>. You can also use {"{{firstName}}"}, {"{{company}}"} and {"{{agentName}}"}.</p>
            </div>
          </FramePanel>
        </Frame>
      )}

      <Frame>
        <FrameHeader title="Call-backs" description="When a lead asks to be called later, the agent calls back at the time they gave." />
        <FramePanel>
          <label className="mb-1.5 block text-label-sm text-text-strong-950" htmlFor="ai-callbacks">Most call-backs per lead</label>
          <Select.Root size="small" value={String(draft.maxCallbacks)} onValueChange={(value) => set("maxCallbacks", Number(value))}>
            <Select.Trigger id="ai-callbacks" className="w-40"><Select.Value /></Select.Trigger>
            <Select.Content>
              {Array.from({ length: AI_CAMPAIGN_MAX_CALLBACKS + 1 }, (_, n) => (
                <Select.Item key={n} value={String(n)}>{n === 0 ? "None" : n}</Select.Item>
              ))}
            </Select.Content>
          </Select.Root>
          <p className="mt-1.5 text-paragraph-xs text-text-sub-600">After the last one, a person takes the lead over.</p>
        </FramePanel>
        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-stroke-soft-200 px-5 py-3.5">
          {(problem || error) && dirty && (
            <p role="alert" className="mr-auto flex items-center gap-2 text-paragraph-sm text-error-base">
              <RiErrorWarningLine className="size-4 shrink-0" />{error ?? problem}
            </p>
          )}
          {dirty && !problem && <span className="text-paragraph-xs text-warning-dark">Unsaved changes</span>}
          {justSaved && !dirty && <span role="status" className="text-paragraph-xs text-success-base">Saved</span>}
          {error && !dirty && <p role="alert" className="mr-auto text-paragraph-sm text-error-base">{error}</p>}
          <Button.Root variant="primary" mode="filled" size="small" onClick={() => void save()} disabled={saving || !dirty || Boolean(problem) || nameTooLong}>
            <Button.Icon as={saving ? RiLoader4Line : RiSaveLine} className={cn(saving && "animate-spin")} />
            {saving ? "Saving…" : "Save settings"}
          </Button.Root>
        </div>
      </Frame>

      <Frame>
        <FrameHeader title="Calling numbers" description="Every lead is called, and messaged, from one of these and keeps hearing from the same one." />
        <FramePanel>
          <NumberPicker stations={stations} selectedIds={numberIds} onChange={(ids) => { setNumbersError(null); setNumberIds(ids); }} error={stationsError} />
          {numbersError && <p role="alert" className="mt-3 text-paragraph-sm text-error-base">{numbersError}</p>}
          <div className="mt-4 flex items-center justify-end gap-3">
            {numbersDirty && <span className="text-paragraph-xs text-warning-dark">Unsaved changes</span>}
            <Button.Root variant="primary" mode="filled" size="small" onClick={() => void saveNumbers()} disabled={savingNumbers || !numbersDirty}>
              <Button.Icon as={savingNumbers ? RiLoader4Line : RiSaveLine} className={cn(savingNumbers && "animate-spin")} />
              {savingNumbers ? "Saving…" : "Save numbers"}
            </Button.Root>
          </div>
        </FramePanel>
        <FrameFooter>Daily limits, gaps and calling hours are the organization&apos;s Sending rules, which each number can override in Settings → WhatsApp → Calling numbers.</FrameFooter>
      </Frame>

      <Frame>
        <FrameHeader title="Pause or archive" description="Pausing stops new calls and messages; leads keep their place. Archiving removes the campaign from the list." />
        <FramePanel className="flex flex-wrap items-center gap-2">
          {launched && (
            <Button.Root variant="neutral" mode="stroke" size="small" onClick={onToggle} disabled={toggling}>
              <Button.Icon as={toggling ? RiLoader4Line : campaign.state === "active" ? RiPauseCircleLine : RiPlayCircleLine} className={cn(toggling && "animate-spin")} />
              {campaign.state === "active" ? "Pause campaign" : "Resume campaign"}
            </Button.Root>
          )}
          <Button.Root variant="error" mode="stroke" size="small" onClick={onArchive}>
            <Button.Icon as={RiArchiveLine} />
            Archive campaign
          </Button.Root>
          {!launched && <p className="text-paragraph-xs text-text-sub-600">This campaign is a draft; launch it from the header once it is ready.</p>}
        </FramePanel>
      </Frame>
    </div>
  );
}
