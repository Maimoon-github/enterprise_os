"use client";

import { useEffect, useRef, useState } from "react";
import { RiLoader4Line, RiPlayFill, RiStopFill } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import { AGENT_VOICES, DEFAULT_AGENT_VOICE } from "@/lib/calls/contract";

/**
 * ▶ beside a voice picker: plays the voice saying a typical opening, in
 * English and Hindi, with the agent's name (GET /api/calling/agent/voice-sample).
 * The first play of a voice takes a few seconds while Gemini speaks it.
 */
export function VoicePreviewButton({ voice, name }: { voice: string | null | undefined; name?: string | null }) {
  const [state, setState] = useState<"idle" | "loading" | "playing">("idle");
  const [error, setError] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);

  const stop = () => {
    audio.current?.pause();
    audio.current = null;
    setState("idle");
  };

  // A different voice or name is a different sample: stop the old one.
  useEffect(() => stop, [voice, name]);

  const play = () => {
    if (state !== "idle") return stop();
    setError(null);
    // A picker's "Default" entry (or nothing chosen) plays the default voice.
    const id = AGENT_VOICES.some((option) => option.id === voice) ? voice! : DEFAULT_AGENT_VOICE;
    const params = new URLSearchParams({ voice: id });
    if (name?.trim()) params.set("name", name.trim());
    const element = new Audio(`/api/calling/agent/voice-sample?${params}`);
    audio.current = element;
    setState("loading");
    element.addEventListener("playing", () => audio.current === element && setState("playing"));
    element.addEventListener("ended", () => audio.current === element && stop());
    element.addEventListener("error", () => {
      if (audio.current !== element) return;
      setError("Could not play the sample");
      stop();
    });
    element.play().catch(() => {
      if (audio.current !== element) return;
      setError("Could not play the sample");
      stop();
    });
  };

  return (
    <span className="inline-flex items-center gap-2">
      <Button.Root
        type="button"
        variant="neutral"
        mode="stroke"
        size="xsmall"
        onClick={play}
        aria-label={state === "idle" ? "Play a sample of this voice" : "Stop the sample"}
        title={state === "idle" ? "Hear this voice" : "Stop"}
      >
        <Button.Icon as={state === "loading" ? RiLoader4Line : state === "playing" ? RiStopFill : RiPlayFill} className={state === "loading" ? "animate-spin" : undefined} />
        {state === "loading" ? "Loading…" : state === "playing" ? "Stop" : "Hear it"}
      </Button.Root>
      {error ? <span className="text-paragraph-xs text-error-base">{error}</span> : null}
    </span>
  );
}
