"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  RiArrowLeftLine,
  RiArrowRightLine,
  RiCheckLine,
  RiDraftLine,
  RiFileExcel2Line,
  RiLoader4Line,
  RiRocketLine,
  RiSmartphoneLine,
  RiStackLine,
  RiTeamLine,
  RiUserAddLine,
} from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import { VoicePreviewButton } from "@/components/calls/VoicePreviewButton";
import { KnowledgePicker } from "./KnowledgePicker";
import * as Input from "@/components/alignui/input";
import * as Select from "@/components/alignui/select";
import * as Textarea from "@/components/alignui/textarea";
import { Frame, FrameHeader, FramePanel } from "@/components/analytics/kit/Frame";
import { TextField } from "@/components/calls/fields";
import AddPeopleToCampaignModal from "@/components/leads/AddPeopleToCampaignModal";
import CampaignCsvMappingDialog from "@/components/leads/CampaignCsvMappingDialog";
import { PageHeader } from "@/components/page/PageHeader";
import { formatDelay } from "@/components/whatsapp/campaigns/metrics";
import {
  AI_CAMPAIGN_MAX_INSTRUCTIONS,
  aiLaunchBlocker,
  aiSequencesError,
  aiSettingsError,
  type AiCampaignDetail,
  type AiLeadsImportResponse,
} from "@/lib/calls/aiCampaigns/api";
import {
  aiLeadsEndpoint,
  aiLeadsUploadEndpoint,
  createAiCampaign,
  getAiCampaign,
  launchAiCampaign,
  setAiCampaignStations,
  updateAiCampaign,
} from "@/lib/calls/aiCampaigns/client";
import { AI_CAMPAIGN_GOALS, AI_CAMPAIGN_GOAL_LABELS, type AiCampaignGoal, type AiCampaignStep } from "@/lib/calls/aiCampaigns/contract";
import { listCallingStations } from "@/lib/calls/client";
import { AGENT_VOICES, DEFAULT_AGENT_NAME, DEFAULT_AGENT_VOICE, MAX_AGENT_NAME_CHARS } from "@/lib/calls/contract";
import type { CallingStation } from "@/lib/calls/stationContract";
import { cn } from "@/utils/cn";
import { errorText, NumberPicker } from "./aiShared";
import { importSummary } from "./AiLeadsTab";
import { AiStepsEditor } from "./AiStepsEditor";

const STEPS = [
  { id: "goal", label: "Name & goal", hint: "What the calls are for", icon: RiDraftLine },
  { id: "numbers", label: "Numbers", hint: "Where calls come from", icon: RiSmartphoneLine },
  { id: "leads", label: "Leads", hint: "People or spreadsheet", icon: RiTeamLine },
  { id: "sequence", label: "Script & sequence", hint: "Instructions and steps", icon: RiStackLine },
  { id: "review", label: "Review & launch", hint: "Confirm readiness", icon: RiCheckLine },
] as const;

const DEFAULT_VOICE = "default";

export function AiCampaignWizard() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState(0);
  const [campaign, setCampaign] = useState<AiCampaignDetail | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [goal, setGoal] = useState<AiCampaignGoal>("book_meeting");
  const [stations, setStations] = useState<CallingStation[] | null>(null);
  const [stationsError, setStationsError] = useState<string | null>(null);
  const [numberIds, setNumberIds] = useState<string[]>([]);
  const [leadCount, setLeadCount] = useState(0);
  const [importNote, setImportNote] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [showPeople, setShowPeople] = useState(false);
  const [instructions, setInstructions] = useState("");
  const [knowledgeIds, setKnowledgeIds] = useState<string[] | null>(null);
  const [agentName, setAgentName] = useState("");
  const [agentVoice, setAgentVoice] = useState(DEFAULT_VOICE);
  const [bookingUrl, setBookingUrl] = useState("");
  const [bookingMessage, setBookingMessage] = useState("");
  const [steps, setSteps] = useState<AiCampaignStep[]>([]);
  const [chaseSteps, setChaseSteps] = useState<AiCampaignStep[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listCallingStations()
      .then((response) => { if (!cancelled) setStations(response.stations); })
      .catch((cause) => { if (!cancelled) setStationsError(errorText(cause, "Could not load numbers")); });
    return () => { cancelled = true; };
  }, []);

  const campaignId = campaign?.id ?? null;

  // Review shows what the server holds, not what this page remembers.
  useEffect(() => {
    if (step !== 4 || !campaignId) return;
    let cancelled = false;
    getAiCampaign(campaignId)
      .then((detail) => { if (!cancelled) { setCampaign(detail); setLeadCount(detail.leads); } })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [step, campaignId]);

  const handover = goal === "human_callback";
  const blocker = campaign
    ? aiLaunchBlocker({ numbers: campaign.numbers.length, steps: campaign.steps, instructions: campaign.instructions, goal: campaign.goal, bookingUrl: campaign.bookingUrl, leads: campaign.leads })
    : "Save the details first";

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  const saveGoal = () => run(async () => {
    if (!name.trim()) throw new Error("Enter a campaign name");
    if (campaign) {
      setCampaign(await updateAiCampaign(campaign.id, { name: name.trim(), description: description.trim() || null, goal }));
    } else {
      const created = await createAiCampaign({ name: name.trim(), description: description.trim() || null });
      const withGoal = goal === created.goal ? created : await updateAiCampaign(created.id, { goal });
      setCampaign(withGoal);
      setInstructions(withGoal.instructions);
      setKnowledgeIds(withGoal.knowledgeIds);
      setBookingMessage(withGoal.bookingMessage);
      setSteps(withGoal.steps.map((s) => ({ ...s })));
      setChaseSteps(withGoal.chaseSteps.map((s) => ({ ...s })));
    }
    setStep(1);
  });

  const saveNumbers = () => run(async () => {
    if (!campaign) return;
    setCampaign(await setAiCampaignStations(campaign.id, numberIds));
    setStep(2);
  });

  const sequenceProblem =
    aiSettingsError({ goal, instructions, bookingUrl: handover ? null : bookingUrl.trim() || null, bookingMessage, maxCallbacks: campaign?.maxCallbacks ?? 2 }) ??
    aiSequencesError(steps, handover ? [] : chaseSteps);

  const saveSequence = () => run(async () => {
    if (!campaign) return;
    if (sequenceProblem) throw new Error(sequenceProblem);
    setCampaign(
      await updateAiCampaign(campaign.id, {
        instructions,
        knowledgeIds,
        agentName: agentName.trim() || null,
        agentVoice: agentVoice === DEFAULT_VOICE ? null : agentVoice,
        bookingUrl: handover ? null : bookingUrl.trim() || null,
        bookingMessage,
        steps,
        chaseSteps,
      }),
    );
    setStep(4);
  });

  const finish = (launch: boolean) => run(async () => {
    if (!campaign) return;
    if (launch) await launchAiCampaign(campaign.id);
    router.push(`/calling/campaigns/ai/${campaign.id}`);
  });

  return (
    <div className="mx-auto w-full max-w-[1440px]">
      <PageHeader
        back={{ href: "/calling/campaigns", label: "Call campaigns" }}
        title="New AI calling campaign"
        description="The AI agent calls your leads by itself from your calling numbers, follows up on WhatsApp, and hands over interested people. It stays a draft until you launch it."
      />

      <div className="mt-6 grid grid-cols-1 items-start gap-4 lg:grid-cols-[280px_minmax(0,1fr)] lg:gap-5">
        <Frame>
          <FrameHeader title="Steps" description={`Step ${step + 1} of ${STEPS.length}`} />
          <FramePanel className="p-2 sm:p-2">
            <ol className="grid grid-cols-2 gap-1 sm:grid-cols-5 lg:grid-cols-1">
              {STEPS.map((item, index) => {
                const active = index === step;
                const reachable = index <= step && (index === 0 || campaign !== null);
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      disabled={!reachable || active || busy}
                      onClick={() => setStep(index)}
                      aria-current={active ? "step" : undefined}
                      className={cn("flex w-full items-center gap-3 rounded-xl p-2.5 text-left transition duration-200 ease-out", active ? "bg-bg-weak-50" : reachable ? "hover:bg-bg-weak-50" : "cursor-default")}
                    >
                      <span className={cn("flex size-7 shrink-0 items-center justify-center rounded-lg text-label-xs transition", index < step ? "bg-success-lighter text-success-base" : active ? "bg-primary-base text-static-white shadow-regular-xs" : "bg-bg-weak-50 text-text-soft-400")}>
                        {index < step ? <RiCheckLine className="size-4" /> : index + 1}
                      </span>
                      <span className="min-w-0">
                        <span className={cn("block text-label-sm", active ? "text-text-strong-950" : "text-text-sub-600")}>{item.label}</span>
                        <span className="mt-0.5 hidden text-paragraph-xs text-text-soft-400 lg:block">{item.hint}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
            <div className="mx-1 mb-1 mt-3 hidden border-t border-stroke-soft-200 px-2 pt-3 lg:block">
              <p className="text-paragraph-xs text-text-soft-400">Summary</p>
              <dl className="mt-2 space-y-2 text-paragraph-sm">
                <SummaryRow label="Name" value={name || "Not named yet"} truncate />
                <SummaryRow label="Goal" value={AI_CAMPAIGN_GOAL_LABELS[goal].label} truncate />
                <SummaryRow label="Numbers" value={numberIds.length.toLocaleString()} />
                <SummaryRow label="Leads" value={leadCount.toLocaleString()} />
                <SummaryRow label="Steps" value={String(steps.length)} />
              </dl>
            </div>
          </FramePanel>
        </Frame>

        <Frame>
          <FramePanel className="min-h-[560px] p-5 sm:p-7">
            {step === 0 && (
              <div className="mx-auto max-w-2xl">
                <Heading title="Name and goal" description="Name the campaign and say what its calls are for." />
                <div className="mt-6 space-y-5">
                  <label className="block">
                    <span className="mb-1.5 block text-label-sm text-text-strong-950">Campaign name</span>
                    <Input.Root hasError={Boolean(error && !name.trim())}>
                      <Input.Wrapper>
                        <Input.Input value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. D2C founders, India" autoFocus />
                      </Input.Wrapper>
                    </Input.Root>
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-label-sm text-text-strong-950">Description <span className="text-text-soft-400">(optional)</span></span>
                    <Textarea.Root simple rows={2} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What is this campaign for?" />
                  </label>
                  <fieldset>
                    <legend className="mb-2 block text-label-sm text-text-strong-950">Goal</legend>
                    <div role="radiogroup" aria-label="Goal" className="grid gap-2">
                      {AI_CAMPAIGN_GOALS.map((value) => {
                        const active = goal === value;
                        return (
                          <button
                            key={value}
                            type="button"
                            role="radio"
                            aria-checked={active}
                            onClick={() => setGoal(value)}
                            className={cn("rounded-xl p-3.5 text-left outline-none ring-1 ring-inset transition focus-visible:ring-2 focus-visible:ring-primary-base", active ? "bg-bg-weak-50 ring-primary-base" : "ring-stroke-soft-200 hover:bg-bg-weak-50")}
                          >
                            <span className="block text-label-sm text-text-strong-950">{AI_CAMPAIGN_GOAL_LABELS[value].label}</span>
                            <span className="mt-1 block text-paragraph-xs text-text-sub-600">{AI_CAMPAIGN_GOAL_LABELS[value].help}</span>
                          </button>
                        );
                      })}
                    </div>
                  </fieldset>
                </div>
                <Footer error={error} backLabel="Cancel" onBack={() => router.push("/calling/campaigns")} onNext={() => void saveGoal()} busy={busy} nextLabel="Continue to numbers" />
              </div>
            )}

            {step === 1 && campaign && (
              <div className="mx-auto max-w-3xl">
                <Heading title="Calling numbers" description="Pick the numbers this campaign calls from. Each lead is called and messaged from one of them and keeps hearing from the same one." />
                <div className="mt-6">
                  <NumberPicker stations={stations} selectedIds={numberIds} onChange={setNumberIds} error={stationsError} />
                  <p className="mt-3 text-paragraph-xs text-text-sub-600">A new number warms up gradually, and every number has its own daily limit and calling hours (Settings → WhatsApp → Calling numbers and Sending rules). You can launch with a number still being linked, but nothing is called until it is.</p>
                </div>
                <Footer error={error} onBack={() => setStep(0)} onNext={() => void saveNumbers()} busy={busy} nextLabel="Continue to leads" />
              </div>
            )}

            {step === 2 && campaign && (
              <div className="mx-auto max-w-3xl">
                <Heading title="Add leads" description="Import a spreadsheet with phone numbers, or select people already in your database." />
                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  <button type="button" onClick={() => fileRef.current?.click()} className="flex min-h-44 flex-col items-center justify-center rounded-2xl border border-dashed border-stroke-sub-300 bg-bg-weak-50 p-6 text-center outline-none transition hover:border-primary-base focus-visible:ring-2 focus-visible:ring-primary-base">
                    <span className="flex size-10 items-center justify-center rounded-xl bg-bg-white-0 ring-1 ring-inset ring-stroke-soft-200"><RiFileExcel2Line className="size-5 text-text-sub-600" /></span>
                    <span className="mt-3 text-label-md text-text-strong-950">Import CSV or Excel</span>
                    <span className="mt-1 text-paragraph-xs text-text-sub-600">You map the phone column before anything is imported.</span>
                  </button>
                  <button type="button" onClick={() => setShowPeople(true)} className="flex min-h-44 flex-col items-center justify-center rounded-2xl bg-bg-white-0 p-6 text-center shadow-regular-xs outline-none ring-1 ring-inset ring-stroke-soft-200 transition hover:bg-bg-weak-50 focus-visible:ring-2 focus-visible:ring-primary-base">
                    <span className="flex size-10 items-center justify-center rounded-xl bg-bg-weak-50 ring-1 ring-inset ring-stroke-soft-200"><RiUserAddLine className="size-5 text-text-sub-600" /></span>
                    <span className="mt-3 text-label-md text-text-strong-950">Add from People</span>
                    <span className="mt-1 text-paragraph-xs text-text-sub-600">Select existing people who already have a phone number.</span>
                  </button>
                </div>
                <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={(event) => setPendingFile(event.target.files?.[0] ?? null)} />
                <div role="status" className="mt-4 rounded-xl bg-bg-weak-50 p-4 ring-1 ring-inset ring-stroke-soft-200">
                  <p className="text-label-sm text-text-strong-950">{leadCount.toLocaleString()} {leadCount === 1 ? "lead" : "leads"} added</p>
                  <p className="mt-1 text-paragraph-xs text-text-sub-600">{importNote ?? "You can continue with no leads and add them later; the campaign cannot launch until it has some."}</p>
                </div>
                <Footer error={error} onBack={() => setStep(1)} onNext={() => setStep(3)} nextLabel="Continue to the script" />
                {pendingFile && (
                  <CampaignCsvMappingDialog
                    file={pendingFile}
                    endpoint={aiLeadsUploadEndpoint(campaign.id)}
                    channel="whatsapp"
                    onClose={() => { setPendingFile(null); if (fileRef.current) fileRef.current.value = ""; }}
                    onImported={(result) => {
                      const imported = result as AiLeadsImportResponse;
                      setLeadCount((current) => current + imported.added);
                      setImportNote(importSummary(imported));
                      setPendingFile(null);
                      if (fileRef.current) fileRef.current.value = "";
                    }}
                  />
                )}
                {showPeople && (
                  <AddPeopleToCampaignModal
                    campaignId={campaign.id}
                    channel="whatsapp"
                    endpoint={aiLeadsEndpoint(campaign.id)}
                    onClose={() => setShowPeople(false)}
                    onAdded={(result) => {
                      setLeadCount((current) => current + result.added);
                      setImportNote(`${result.added} added from People${result.skippedDuplicate ? ` · ${result.skippedDuplicate} already in the campaign` : ""}${result.skippedMissingIdentity ? ` · ${result.skippedMissingIdentity} without a phone number` : ""}`);
                    }}
                  />
                )}
              </div>
            )}

            {step === 3 && campaign && (
              <div>
                <Heading title="Script and sequence" description="What every call is about, who the agent is, and the calls and messages to send. The defaults are a sensible start." />
                <div className="mt-6 grid gap-6">
                  <div>
                    <label className="mb-1.5 block text-label-sm text-text-strong-950">Knowledge</label>
                    <KnowledgePicker value={knowledgeIds} onChange={setKnowledgeIds} />
                  </div>
                  <div>
                    <label htmlFor="wiz-instructions" className="mb-1.5 block text-label-sm text-text-strong-950">Campaign instructions</label>
                    <p className="mb-2 text-paragraph-xs text-text-sub-600">What every call is about, on top of the Knowledge above: who you are calling, what you offer, what to find out.</p>
                    <Textarea.Root id="wiz-instructions" simple rows={6} maxLength={AI_CAMPAIGN_MAX_INSTRUCTIONS} value={instructions} onChange={(event) => setInstructions(event.target.value)} placeholder="You are calling founders of D2C brands who run Meta ads. We help them …" hasError={!instructions.trim()} />
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <TextField label="Agent name" value={agentName} onChange={setAgentName} placeholder={DEFAULT_AGENT_NAME} maxLength={MAX_AGENT_NAME_CHARS + 10} />
                    <div>
                      <label className="mb-1.5 block text-label-sm text-text-strong-950">Voice</label>
                      <div className="flex items-center gap-2">
                        <div className="min-w-0 flex-1">
                          <Select.Root size="small" value={agentVoice} onValueChange={setAgentVoice}>
                            <Select.Trigger aria-label="Voice"><Select.Value /></Select.Trigger>
                            <Select.Content>
                              <Select.Item value={DEFAULT_VOICE}>Default ({DEFAULT_AGENT_VOICE})</Select.Item>
                              {AGENT_VOICES.map((voice) => <Select.Item key={voice.id} value={voice.id}>{voice.label}</Select.Item>)}
                            </Select.Content>
                          </Select.Root>
                        </div>
                        <VoicePreviewButton voice={agentVoice} name={agentName} />
                      </div>
                    </div>
                  </div>
                  {!handover && (
                    <div className="space-y-3">
                      <TextField label="Booking link (Cal.com)" value={bookingUrl} onChange={setBookingUrl} placeholder="https://cal.com/acme/30min" inputMode="url" />
                      <div>
                        <label htmlFor="wiz-booking-message" className="mb-1.5 block text-label-sm text-text-strong-950">Booking message</label>
                        <Textarea.Root id="wiz-booking-message" simple rows={3} value={bookingMessage} onChange={(event) => setBookingMessage(event.target.value)} hasError={Boolean(bookingUrl.trim()) && !bookingMessage.includes("{{bookingLink}}")} />
                        <p className="mt-1 text-paragraph-xs text-text-sub-600">The WhatsApp sent right after they agree to book. Must include <code className="font-mono">{"{{bookingLink}}"}</code>.</p>
                      </div>
                    </div>
                  )}
                  <div>
                    <h3 className="mb-3 text-label-md text-text-strong-950">Reach them</h3>
                    <AiStepsEditor steps={steps} onChange={setSteps} campaignId={campaign.id} agentName={agentName.trim() || null} agentVoice={agentVoice === DEFAULT_VOICE ? null : agentVoice} statsPhase="reach" emptyText="Add at least one call." />
                  </div>
                  {!handover && (
                    <div>
                      <h3 className="text-label-md text-text-strong-950">If they said yes but haven&apos;t booked</h3>
                      <p className="mb-3 mt-1 text-paragraph-xs text-text-sub-600">Runs after the booking message, until they book, reply, or the steps run out and a person takes over.</p>
                      <AiStepsEditor steps={chaseSteps} onChange={setChaseSteps} allowEmpty campaignId={campaign.id} agentName={agentName.trim() || null} agentVoice={agentVoice === DEFAULT_VOICE ? null : agentVoice} statsPhase="chase" emptyText="No follow-ups." />
                    </div>
                  )}
                </div>
                <Footer error={error} onBack={() => setStep(2)} onNext={() => void saveSequence()} busy={busy} nextDisabled={Boolean(sequenceProblem)} nextLabel="Save and review" />
                {sequenceProblem && <p className="mt-2 text-right text-paragraph-xs text-error-base">{sequenceProblem}</p>}
              </div>
            )}

            {step === 4 && campaign && (
              <div className="mx-auto max-w-3xl">
                <Heading title="Review and launch" description="Nothing is called until you launch. You can save it as a draft and finish later." />
                <div className="mt-6 grid gap-3 sm:grid-cols-4">
                  <SummaryCard label="Campaign" value={campaign.name} detail={AI_CAMPAIGN_GOAL_LABELS[campaign.goal].label} />
                  <SummaryCard label="Leads" value={campaign.leads.toLocaleString()} detail="queued to be called" />
                  <SummaryCard label="Numbers" value={campaign.numbers.length.toLocaleString()} detail={`${campaign.numbers.filter((n) => n.status === "active").length} active`} />
                  <SummaryCard label="Agent" value={campaign.agentName || DEFAULT_AGENT_NAME} detail={campaign.agentVoice || DEFAULT_AGENT_VOICE} />
                </div>
                <div className="mt-4 rounded-2xl bg-bg-weak-50 p-1 ring-1 ring-inset ring-stroke-soft-200">
                  <h3 className="px-3 pb-2 pt-2 text-label-sm text-text-strong-950">Sequence</h3>
                  <ul className="divide-y divide-stroke-soft-200 rounded-xl bg-bg-white-0 px-4 ring-1 ring-inset ring-stroke-soft-200">
                    {campaign.steps.map((item, index) => (
                      <li key={item.id} className="flex items-center justify-between gap-4 py-2.5 text-paragraph-sm">
                        <span className="min-w-0">
                          <span className="block text-text-sub-600">{item.kind === "call" ? "AI call" : "WhatsApp message"}{index > 0 ? ` · after ${formatDelay(item.delayHours)}` : " · first"}</span>
                          <span className="block max-w-md truncate text-paragraph-xs text-text-soft-400">{item.kind === "call" ? item.instructions || "No extra instructions" : item.body}</span>
                        </span>
                        <RiCheckLine className="size-4 shrink-0 text-success-base" aria-hidden="true" />
                      </li>
                    ))}
                  </ul>
                  {campaign.goal !== "human_callback" && campaign.chaseSteps.length > 0 && (
                    <p className="px-3 py-2 text-paragraph-xs text-text-sub-600">Then {campaign.chaseSteps.length} follow-up {campaign.chaseSteps.length === 1 ? "step" : "steps"} for leads who say yes but do not book.</p>
                  )}
                </div>
                <p className="mt-4 text-paragraph-xs text-text-sub-600">Calls start within the numbers&apos; calling hours, spaced out and capped per day. A reply on any channel stops the sequence and lands in CRM → Action required.</p>
                {blocker && <p className="mt-4 rounded-xl bg-warning-lighter p-3 text-paragraph-sm text-warning-dark">{blocker} before launching. You can save it as a draft and finish later.</p>}
                <Footer error={error} onBack={() => setStep(3)} busy={busy} secondaryLabel="Save as draft" onSecondary={() => void finish(false)} nextLabel="Launch campaign" onNext={() => void finish(true)} nextDisabled={Boolean(blocker)} nextIcon={RiRocketLine} />
              </div>
            )}
          </FramePanel>
        </Frame>
      </div>
    </div>
  );
}

function SummaryRow({ label, value, truncate }: { label: string; value: string; truncate?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-text-sub-600">{label}</dt>
      <dd className={cn("text-label-sm tabular-nums text-text-strong-950", truncate && "min-w-0 truncate")}>{value}</dd>
    </div>
  );
}

function Heading({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h2 className="text-label-lg text-text-strong-950">{title}</h2>
      <p className="mt-1 text-paragraph-sm text-text-sub-600">{description}</p>
    </div>
  );
}

function SummaryCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-xl bg-bg-white-0 p-4 shadow-regular-xs ring-1 ring-inset ring-stroke-soft-200">
      <p className="text-paragraph-xs text-text-sub-600">{label}</p>
      <p className="mt-1 truncate text-label-lg text-text-strong-950" title={value}>{value}</p>
      <p className="truncate text-paragraph-xs text-text-sub-600">{detail}</p>
    </div>
  );
}

function Footer({
  error,
  onBack,
  onNext,
  busy,
  backLabel = "Back",
  nextLabel,
  nextDisabled,
  secondaryLabel,
  onSecondary,
  nextIcon: NextIcon = RiArrowRightLine,
}: {
  error?: string | null;
  onBack: () => void;
  onNext: () => void;
  busy?: boolean;
  backLabel?: string;
  nextLabel: string;
  nextDisabled?: boolean;
  secondaryLabel?: string;
  onSecondary?: () => void;
  nextIcon?: typeof RiArrowRightLine;
}) {
  return (
    <div className="mt-8 border-t border-stroke-soft-200 pt-5">
      {error && <p role="alert" className="mb-3 text-paragraph-sm text-error-base">{error}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button.Root variant="neutral" mode="ghost" size="small" onClick={onBack} disabled={busy}>
          <Button.Icon as={RiArrowLeftLine} />{backLabel}
        </Button.Root>
        <div className="flex gap-2">
          {secondaryLabel && onSecondary && <Button.Root variant="neutral" mode="stroke" size="small" onClick={onSecondary} disabled={busy}>{secondaryLabel}</Button.Root>}
          <Button.Root variant="primary" mode="filled" size="small" onClick={onNext} disabled={busy || nextDisabled}>
            <Button.Icon as={busy ? RiLoader4Line : NextIcon} className={cn(busy && "animate-spin")} />
            {busy ? "Saving…" : nextLabel}
          </Button.Root>
        </div>
      </div>
    </div>
  );
}
