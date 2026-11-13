"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { RiCloseLine, RiErrorWarningLine, RiLoader4Line, RiMicLine, RiMicOffLine, RiPhoneFill, RiVolumeUpLine } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import { cn } from "@/utils/cn";
import { formatElapsed } from "./formatElapsed";
import {
  dismissRemoteRepCall,
  hangUpRemoteRepCall,
  remoteRepCallSnapshot,
  resumeRemoteRepAudio,
  setRemoteRepMuted,
  subscribeRemoteRepCall,
  type RemoteRepCallState,
} from "./remoteRepCall";
import { isRemoteRepOver } from "./remoteRepStage";

/** A call that ended normally leaves the bar after this; a failure stays until dismissed. */
const ENDED_HIDE_MS = 10_000;

/**
 * The floating bar for a call the rep talks on through a calling number
 * (remoteRepCall.ts): who, where it stands, mute and hang up. Mounted once in
 * the root layout, so it stays on screen across pages while the call is on.
 */
export function RemoteRepCallBar() {
  const call = useSyncExternalStore(subscribeRemoteRepCall, remoteRepCallSnapshot, () => null);
  const [hangingUp, setHangingUp] = useState(false);

  const stage = call?.stage;
  useEffect(() => {
    if (stage !== "ended") return;
    const timer = window.setTimeout(dismissRemoteRepCall, ENDED_HIDE_MS);
    return () => window.clearTimeout(timer);
  }, [stage]);

  if (!call) return null;
  const over = isRemoteRepOver(call.stage);

  const hangUp = async () => {
    setHangingUp(true);
    try {
      await hangUpRemoteRepCall();
    } finally {
      setHangingUp(false);
    }
  };

  return (
    <div
      role="region"
      aria-label="Call"
      // pointer-events-auto: a modal (the lead drawer) sets pointer-events: none on <body>.
      className="pointer-events-auto fixed inset-x-4 bottom-4 z-[90] mx-auto max-w-md rounded-2xl bg-bg-white-0 p-3 shadow-regular-md ring-1 ring-inset ring-stroke-soft-200 animate-in fade-in-0 slide-in-from-bottom-2 sm:inset-x-auto sm:left-1/2 sm:w-[26rem] sm:-translate-x-1/2"
    >
      <div className="flex items-center gap-3">
        <StageIcon call={call} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-label-sm text-text-strong-950">
            {call.leadName}
            {call.numberName && <span className="font-normal text-text-soft-400"> · from {call.numberName}</span>}
          </p>
          <p aria-live="polite" className={cn("text-paragraph-xs", call.stage === "error" ? "text-error-dark" : "text-text-sub-600")}>
            <StageText call={call} />
          </p>
        </div>
        {!over ? (
          <div className="flex shrink-0 items-center gap-1.5">
            <Button.Root
              variant="neutral"
              mode="stroke"
              size="xsmall"
              aria-pressed={call.muted}
              aria-label={call.muted ? "Unmute" : "Mute"}
              title={call.muted ? "Unmute" : "Mute"}
              disabled={call.stage === "mic"}
              onClick={() => setRemoteRepMuted(!call.muted)}
            >
              <Button.Icon as={call.muted ? RiMicOffLine : RiMicLine} className={cn(call.muted && "text-error-base")} />
            </Button.Root>
            <Button.Root variant="error" mode="filled" size="xsmall" disabled={call.stage === "mic" || hangingUp} onClick={() => void hangUp()}>
              <Button.Icon as={hangingUp ? RiLoader4Line : RiPhoneFill} className={cn("rotate-[135deg]", hangingUp && "animate-spin")} />
              {call.stage === "on-call" ? "Hang up" : "Cancel"}
            </Button.Root>
          </div>
        ) : (
          <Button.Root variant="neutral" mode="ghost" size="xsmall" aria-label="Close" title="Close" onClick={dismissRemoteRepCall}>
            <Button.Icon as={RiCloseLine} />
          </Button.Root>
        )}
      </div>
      {!over && call.audioBlocked && (
        <Button.Root variant="primary" mode="lighter" size="xxsmall" className="mt-2 w-full" onClick={resumeRemoteRepAudio}>
          <Button.Icon as={RiVolumeUpLine} />
          The browser paused the call audio — click to hear them
        </Button.Root>
      )}
      {!over && call.stage !== "mic" && (
        <p className="mt-2 text-paragraph-xs text-text-soft-400">
          {call.stage === "on-call" ? "Use headphones for the best sound." : "Keep this tab open — the call runs through it. Use headphones for the best sound."}
        </p>
      )}
    </div>
  );
}

function StageIcon({ call }: { call: RemoteRepCallState }) {
  if (call.stage === "on-call") {
    return (
      <span className="relative flex size-2.5 shrink-0" aria-hidden="true">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-success-base opacity-75" />
        <span className="relative inline-flex size-2.5 rounded-full bg-success-base" />
      </span>
    );
  }
  if (call.stage === "error") return <RiErrorWarningLine className="size-4 shrink-0 text-error-base" aria-hidden="true" />;
  if (call.stage === "ended") return <RiPhoneFill className="size-4 shrink-0 rotate-[135deg] text-text-soft-400" aria-hidden="true" />;
  return <RiLoader4Line className="size-4 shrink-0 animate-spin text-text-sub-600" aria-hidden="true" />;
}

function StageText({ call }: { call: RemoteRepCallState }) {
  const number = call.numberName ?? "the number";
  switch (call.stage) {
    case "mic":
      return <>Getting your microphone…</>;
    case "placing":
      return <>Placing the call…</>;
    case "waiting":
      return <>Waiting for {number} to be free…</>;
    case "opening":
      return <>Opening {number}&apos;s WhatsApp…</>;
    case "dialing":
      return <>Calling…</>;
    case "ringing":
      return <>Ringing…</>;
    case "on-call":
      return (
        <>
          On call · <OnCallTimer answeredAt={call.answeredAt} />
          {call.muted && " · muted"}
          {call.unstable && " · connection unstable…"}
        </>
      );
    case "ended":
    case "error":
      return <>{call.message ?? (call.stage === "error" ? "The call failed" : "Call ended")}</>;
  }
}

function OnCallTimer({ answeredAt }: { answeredAt: number | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);
  return <span className="tabular-nums">{answeredAt ? formatElapsed(now - answeredAt) : "0:00"}</span>;
}
