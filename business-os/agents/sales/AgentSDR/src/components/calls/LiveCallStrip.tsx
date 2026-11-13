"use client";

import { useEffect, useState } from "react";
import { RiCheckboxCircleLine, RiCloseCircleLine, RiErrorWarningLine, RiLoader4Line } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import { Frame, FramePanel } from "@/components/analytics/kit/Frame";
import { FormError } from "./fields";
import { cancelCall, endCallViaRecorder } from "@/lib/calls/client";
import type { AgentOutcome, CallStatus } from "@/lib/calls/contract";
import type { CloudCallPhase } from "@/lib/calls/stationContract";
import { AgentOutcomeLine } from "./AgentOutcomeLine";
import { formatElapsed } from "./formatElapsed";
import { useLiveCallState } from "./useLiveCall";

/** A connected call: hanging up from AgentSDR ends it, and its recording is kept. */
const END_CALL_PHASES: ReadonlySet<CloudCallPhase["kind"]> = new Set(["on-call"]);
/** A call not yet connected: the rep can cancel it. */
const CANCEL_PHASES: ReadonlySet<CloudCallPhase["kind"]> = new Set([
  "queued",
  "starting-browser",
  "opening",
  "calling",
  "ringing",
  "manual-dial",
  "audio-blocked",
]);

/**
 * `serverStatus` is the call's status as AgentSDR last loaded it. A call the
 * server has closed out as not connected or failed (cancelled, WhatsApp
 * closed, never reported back) may still show "Calling…" here, because its
 * extension went quiet; the server's word wins and the strip goes away.
 */
export function LiveCallStrip({
  callId,
  serverStatus,
  agentOutcome,
  onCancelled,
}: {
  callId: string | null;
  serverStatus?: CallStatus | null;
  /** What the AI agent reported for this call, once it has. */
  agentOutcome?: AgentOutcome | null;
  /** After a cancel, so the parent can reload the call. */
  onCancelled?: () => void;
}) {
  const { phase, cloud } = useLiveCallState(callId);
  const [ending, setEnding] = useState(false);
  const [endError, setEndError] = useState("");

  // A rejection from one phase shouldn't linger once the extension moves on
  // (e.g. the call ended on its own right after a rejected end-call click).
  // Adjusted during render rather than in an effect, per React's own
  // guidance for resetting state when a derived value changes — it avoids
  // the extra render an effect-based reset would cause.
  const [lastPhaseKind, setLastPhaseKind] = useState(phase?.kind);
  if (phase?.kind !== lastPhaseKind) {
    setLastPhaseKind(phase?.kind);
    if (endError) setEndError("");
  }

  if (!phase) return null;
  const closedOnServer = serverStatus === "no_recording" || serverStatus === "failed";
  if (closedOnServer && (CANCEL_PHASES.has(phase.kind) || END_CALL_PHASES.has(phase.kind))) return null;

  const cancel = async () => {
    if (!callId) return;
    setEnding(true);
    setEndError("");
    try {
      // Hang up in WhatsApp if the call is still there — it may not be,
      // which is often why it is being cancelled — then close it out here.
      // (A cloud call has no extension in this browser to ask.)
      if (!cloud) await endCallViaRecorder(callId).catch(() => {});
      await cancelCall(callId);
      onCancelled?.();
    } catch (cause) {
      setEndError(cause instanceof Error ? cause.message : "Couldn't cancel the call. Please try again.");
    } finally {
      setEnding(false);
    }
  };

  const endCall = async () => {
    if (!callId) return;
    setEnding(true);
    setEndError("");
    try {
      await endCallViaRecorder(callId);
    } catch (cause) {
      setEndError(cause instanceof Error ? cause.message : "Couldn't end the call. Please try again.");
    } finally {
      setEnding(false);
    }
  };

  return (
    <Frame aria-label="Live call">
      <FramePanel className="space-y-2 p-3 sm:p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <PhaseDot phase={phase} />
            <p aria-live="polite" className="min-w-0 text-label-sm text-text-strong-950">
              <PhaseStatus phase={phase} />
            </p>
            {cloud && (
              <span className="shrink-0 text-paragraph-xs text-text-soft-400">
                {cloud.remoteRep ? "Rep" : "AI agent"}{cloud.stationName ? ` · ${cloud.stationName}` : ""}
              </span>
            )}
          </div>
          {END_CALL_PHASES.has(phase.kind) && !cloud && (
            <Button.Root
              variant="error"
              mode="stroke"
              size="xxsmall"
              className="shrink-0 gap-1.5 text-label-xs"
              disabled={ending || !callId}
              onClick={() => void endCall()}
            >
              {ending
                ? <RiLoader4Line className="size-3.5 animate-spin" aria-hidden="true" />
                : <RiCloseCircleLine className="size-3.5" aria-hidden="true" />}
              End call
            </Button.Root>
          )}
          {CANCEL_PHASES.has(phase.kind) && (
            <Button.Root
              variant="error"
              mode="stroke"
              size="xxsmall"
              className="shrink-0 gap-1.5 text-label-xs"
              disabled={ending || !callId}
              onClick={() => void cancel()}
            >
              {ending
                ? <RiLoader4Line className="size-3.5 animate-spin" aria-hidden="true" />
                : <RiCloseCircleLine className="size-3.5" aria-hidden="true" />}
              Cancel call
            </Button.Root>
          )}
        </div>
        <PhaseDetail phase={phase} />
        {agentOutcome && <AgentOutcomeLine outcome={agentOutcome} />}
        {endError && <FormError>{endError}</FormError>}
      </FramePanel>
    </Frame>
  );
}

function PhaseDot({ phase }: { phase: CloudCallPhase }) {
  switch (phase.kind) {
    case "queued":
    case "starting-browser":
    case "opening":
    case "calling":
    case "ringing":
    case "manual-dial":
    case "audio-blocked":
    case "processing":
      return <RiLoader4Line className="size-3.5 shrink-0 animate-spin text-text-sub-600" aria-hidden="true" />;
    case "on-call":
      return (
        <span className="relative flex size-2.5 shrink-0" aria-hidden="true">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-error-base opacity-75" />
          <span className="relative inline-flex size-2.5 rounded-full bg-error-base" />
        </span>
      );
    case "done":
      return <RiCheckboxCircleLine className="size-3.5 shrink-0 text-success-base" aria-hidden="true" />;
    case "error":
      return <RiErrorWarningLine className="size-3.5 shrink-0 text-error-base" aria-hidden="true" />;
    case "not-answered":
    case "not-on-whatsapp":
      return <span className="size-2.5 shrink-0 rounded-full bg-text-soft-400" aria-hidden="true" />;
  }
}

function PhaseStatus({ phase }: { phase: CloudCallPhase }) {
  switch (phase.kind) {
    case "queued":
      return <>Waiting for a cloud number…</>;
    case "starting-browser":
      return <>Opening WhatsApp in the cloud…</>;
    case "opening":
      return <>Opening WhatsApp…</>;
    case "calling":
      return <>Calling…</>;
    case "ringing":
      return <>Ringing — recording starts when they pick up</>;
    case "on-call":
      return <>Recording</>;
    case "manual-dial":
      return <>Couldn&apos;t press Voice call — switch to WhatsApp and click it; recording still starts on its own</>;
    case "audio-blocked":
      return <>Chrome paused the call audio — switch to the WhatsApp tab and click anywhere</>;
    case "not-answered":
      return <>Not answered — nothing was recorded</>;
    case "not-on-whatsapp":
      return phase.noCallButton ? (
        <>WhatsApp can&apos;t call this number (a business account, likely) — marked Not on WhatsApp</>
      ) : (
        <>This number isn&apos;t on WhatsApp</>
      );
    case "processing":
      return <>{phase.step === "uploading" ? "Saving the recording…" : "Transcribing…"}</>;
    case "done":
      return <>Call recorded ({formatElapsed(phase.durationMs)})</>;
    case "error":
      return <>{phase.message}</>;
  }
}

function PhaseDetail({ phase }: { phase: CloudCallPhase }) {
  switch (phase.kind) {
    case "on-call":
      return (
        <div className="space-y-1">
          <p className="text-paragraph-sm tabular-nums text-text-sub-600">
            <LiveTimer answeredAt={phase.answeredAt} />
          </p>
          {!phase.timerSeen && (
            <p className="text-paragraph-xs text-text-soft-400">Call timer not detected — recording started as a fallback</p>
          )}
        </div>
      );
    case "processing":
      return <p className="text-paragraph-sm tabular-nums text-text-sub-600">{formatElapsed(phase.durationMs)}</p>;
    case "done":
      if (phase.transcriptFailed) {
        return <p className="text-paragraph-xs text-error-dark">Transcription failed — retry below</p>;
      }
      return phase.summary ? <p className="line-clamp-4 text-paragraph-sm text-text-sub-600">{phase.summary}</p> : null;
    case "error":
      return phase.savedLocally ? <p className="text-paragraph-xs text-text-soft-400">The recording was saved to your Downloads.</p> : null;
    default:
      return null;
  }
}

/** A live mm:ss ticking up from `answeredAt` (epoch ms), 1s resolution. */
function LiveTimer({ answeredAt }: { answeredAt: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);
  return <>{formatElapsed(now - answeredAt)}</>;
}
