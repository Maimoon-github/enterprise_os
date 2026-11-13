"use client";

import { useEffect, useRef, useState } from "react";
import { RiLoader4Line, RiMicLine, RiPhoneFill, RiPhoneLine } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import type { AgentTokenResponse } from "@/lib/calls/contract";
import { createDownsampler } from "../../../extensions/whatsapp-recorder/src/downsample";
import { LiveAgent } from "../../../extensions/whatsapp-recorder/src/live-agent";
import { toolLabel, type Tool } from "./AgentRehearsal";

type Line = { who: "lead" | "agent"; text: string; cut?: boolean } | { who: "tool"; tool: Tool };
type Phase = "idle" | "connecting" | "ringing" | "live" | "ended";

/** The mic is sent in ~40 ms blocks, as the extension sends a call's audio. */
const BLOCK_SECONDS = 0.04;
/** "Connecting…" on a real call: the greeting is prepared, then the lead picks up. */
const PICKUP_AFTER_MS = 1_000;

/** A worklet that hands the microphone's samples to the page, block by block. */
const TAP_WORKLET = `
class AgentsdrTap extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) this.port.postMessage(channel.slice(0));
    return true;
  }
}
registerProcessor("agentsdr-tap", AgentsdrTap);
`;

/**
 * A rehearsal call by voice: talk to the AI agent with your microphone and
 * hear it answer, with the exact session a campaign call gets — the token
 * comes from POST /api/calling/agent/rehearse/voice, and the agent is the
 * extension's own LiveAgent (greeting held for your hello, silence
 * check-ins, outcome, hanging up after its goodbye). Nothing is placed or
 * saved.
 */
export function AgentVoiceRehearsal({ campaignId, contactId, stepId, brief, name, voice }: {
  campaignId?: string;
  /** Rehearse as this lead of the campaign: their name, company, history and own instructions. */
  contactId?: string;
  stepId?: string;
  brief?: string;
  name?: string;
  voice?: string;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [lines, setLines] = useState<Line[]>([]);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const stopRef = useRef<(() => void) | null>(null);
  const scroller = useRef<HTMLDivElement | null>(null);

  useEffect(() => () => stopRef.current?.(), []);
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [lines]);
  useEffect(() => {
    if (phase !== "live") return;
    const started = Date.now();
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500);
    return () => window.clearInterval(timer);
  }, [phase]);

  async function start() {
    setError(null);
    setLines([]);
    setLog([]);
    setSeconds(0);
    setPhase("connecting");

    // Created in the click, so the browser lets it play.
    const context = new AudioContext();
    let microphone: MediaStream;
    try {
      microphone = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch {
      void context.close();
      setPhase("idle");
      setError("Allow the microphone to rehearse by voice.");
      return;
    }

    let ended = false;
    let playHead = 0;
    const playing = new Set<AudioBufferSourceNode>();
    let hangupTimer = 0;
    let pickupTimer = 0;
    let tap: AudioWorkletNode | null = null;
    let source: MediaStreamAudioSourceNode | null = null;

    const stop = (why?: string) => {
      if (ended) return;
      ended = true;
      window.clearTimeout(hangupTimer);
      window.clearTimeout(pickupTimer);
      agent.close();
      tap?.port.close();
      tap?.disconnect();
      source?.disconnect();
      for (const node of playing) node.stop();
      microphone.getTracks().forEach((track) => track.stop());
      void context.close();
      stopRef.current = null;
      setPhase("ended");
      if (why) setLog((current) => [...current, why]);
    };

    const agent = new LiveAgent({
      play(pcm, rate) {
        if (ended) return;
        const samples = new Int16Array(pcm);
        const buffer = context.createBuffer(1, samples.length, rate);
        const channel = buffer.getChannelData(0);
        for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 0x8000;
        const node = context.createBufferSource();
        node.buffer = buffer;
        node.connect(context.destination);
        const at = Math.max(context.currentTime + 0.02, playHead);
        node.start(at);
        playHead = at + buffer.duration;
        playing.add(node);
        node.onended = () => playing.delete(node);
      },
      interrupt() {
        for (const node of playing) node.stop();
        playing.clear();
        playHead = context.currentTime;
      },
      hangup(reason) {
        // As on a call: let the goodbye finish, then hang up.
        const remaining = Math.max(0, playHead - context.currentTime) * 1000;
        hangupTimer = window.setTimeout(() => stop(`The agent hung up (${reason}).`), remaining + 600);
      },
      trace(step) {
        setLog((current) => [...current.slice(-80), step]);
        // start() reports a refused token, and the session dropping, only here.
        const failed = /^AI agent: (no session — .*|disconnected .*)$/.exec(step);
        if (failed && !ended) {
          setError(failed[1]!.replace(/^no session — /, "Could not start the agent: "));
          stop();
        }
      },
      async token() {
        try {
          const response = await fetch("/api/calling/agent/rehearse/voice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ campaignId, contactId, stepId, brief, name, voice }),
          });
          const body = (await response.json().catch(() => null)) as (AgentTokenResponse & { error?: string }) | null;
          if (!response.ok || !body?.token) return { ok: false, error: body?.error ?? `HTTP ${response.status}` };
          return { ok: true, ...body };
        } catch (caught) {
          return { ok: false, error: caught instanceof Error ? caught.message : String(caught) };
        }
      },
      outcome(report) {
        setLines((current) => [...current, { who: "tool", tool: { name: "record_outcome", args: report } }]);
      },
      ready() {
        if (ended) return;
        // WhatsApp shows "Connecting…": the greeting is prepared; then the lead picks up.
        agent.prepareGreeting();
        setPhase("ringing");
        pickupTimer = window.setTimeout(() => {
          if (ended) return;
          agent.greet();
          setPhase("live");
        }, PICKUP_AFTER_MS);
      },
      transcript(who, text, why) {
        setLines((current) => [...current, { who, text, cut: why === "interrupted" }]);
      },
    });
    stopRef.current = () => stop();

    try {
      await context.audioWorklet.addModule(URL.createObjectURL(new Blob([TAP_WORKLET], { type: "application/javascript" })));
      source = context.createMediaStreamSource(microphone);
      tap = new AudioWorkletNode(context, "agentsdr-tap");
      const downsample = createDownsampler(context.sampleRate, 16_000);
      const blockSize = Math.round(context.sampleRate * BLOCK_SECONDS);
      let pending = new Float32Array(0);
      tap.port.onmessage = (event: MessageEvent<Float32Array>) => {
        if (ended) return;
        const joined = new Float32Array(pending.length + event.data.length);
        joined.set(pending);
        joined.set(event.data, pending.length);
        pending = joined;
        while (pending.length >= blockSize) {
          const pcm = downsample(pending.subarray(0, blockSize));
          pending = pending.slice(blockSize);
          if (pcm.length) agent.sendAudio(pcm.buffer);
        }
      };
      source.connect(tap);
      await agent.start();
    } catch (caught) {
      stop();
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  const busy = phase === "connecting" || phase === "ringing" || phase === "live";
  const minutes = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-stroke-soft-200 bg-bg-white-0 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-paragraph-xs text-text-sub-600">
          Talk to the agent with your microphone, as the lead would. Use headphones, so it does not hear itself. No call is placed.
        </p>
        {busy ? (
          <Button.Root variant="error" mode="filled" size="xsmall" onClick={() => stopRef.current?.()}>
            <Button.Icon as={RiPhoneFill} className="rotate-[135deg]" />
            Hang up
          </Button.Root>
        ) : (
          <Button.Root variant="primary" mode="filled" size="xsmall" onClick={() => void start()}>
            <Button.Icon as={RiPhoneLine} />
            {phase === "ended" ? "Call again" : "Start rehearsal call"}
          </Button.Root>
        )}
      </div>

      {phase !== "idle" && (
        <div className="flex items-center gap-2 text-paragraph-xs text-text-sub-600">
          {phase === "connecting" || phase === "ringing" ? (
            <RiLoader4Line className="size-4 animate-spin" aria-hidden />
          ) : phase === "live" ? (
            <RiMicLine className="size-4 text-success-base" aria-hidden />
          ) : null}
          <span>
            {phase === "connecting" && "Connecting to the agent…"}
            {phase === "ringing" && "Connecting… (it is preparing its greeting)"}
            {phase === "live" && `On the call · ${minutes} — say hello`}
            {phase === "ended" && `Call ended · ${minutes}`}
          </span>
        </div>
      )}

      {lines.length > 0 && (
        <div ref={scroller} className="flex max-h-80 flex-col gap-2 overflow-y-auto">
          {lines.map((line, index) =>
            line.who === "tool" ? (
              <span key={index} className="self-start rounded-md bg-bg-weak-50 px-2 py-0.5 text-subheading-2xs text-text-sub-600">
                {toolLabel(line.tool)}
              </span>
            ) : (
              <div key={index} className={line.who === "lead" ? "flex justify-end" : "flex justify-start"}>
                <div
                  className={
                    line.who === "lead"
                      ? "max-w-[85%] rounded-xl bg-bg-weak-50 px-3 py-2 text-paragraph-sm text-text-strong-950"
                      : "max-w-[85%] rounded-xl bg-information-lighter px-3 py-2 text-paragraph-sm text-text-strong-950"
                  }
                >
                  {line.text}
                  {line.cut ? <span className="text-text-soft-400"> — (you cut in)</span> : null}
                </div>
              </div>
            ),
          )}
        </div>
      )}

      {error ? <p className="text-paragraph-xs text-error-base">{error}</p> : null}

      {log.length > 0 && (
        <details className="text-paragraph-xs text-text-sub-600">
          <summary className="cursor-pointer select-none">Timing log</summary>
          <ol className="mt-2 max-h-48 space-y-0.5 overflow-y-auto font-mono text-[11px] leading-4">
            {log.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
