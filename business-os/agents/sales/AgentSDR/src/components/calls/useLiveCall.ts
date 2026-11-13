"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import { useEffect, useState } from "react";
import { getCall, subscribeToCallUpdates } from "@/lib/calls/client";
import { TERMINAL_CALL_STATUSES, type CallDetail, type RecorderCallPhase } from "@/lib/calls/contract";
import type { CloudCallPhase } from "@/lib/calls/stationContract";

/** How often a cloud call is re-read; its extension is in a browser this tab cannot hear. */
const CLOUD_POLL_MS = 2000;

/** The phase a finished cloud call ended in, when its worker never reported one (it failed before the extension ran). */
function terminalPhase(call: CallDetail): CloudCallPhase | null {
  if (call.livePhase) return call.livePhase;
  if (call.status === "failed") return { kind: "error", message: call.error ?? "The call failed.", savedLocally: false };
  return null;
}

export type LiveCallState = {
  phase: CloudCallPhase | null;
  /** Set for a call placed from a cloud calling station — by the AI agent, or a rep talking from AgentSDR (`remoteRep`). */
  cloud: { stationName: string | null; remoteRep: boolean } | null;
};

/**
 * The latest phase for `callId`, and whether it is a cloud call. A rep's
 * call is reported by the recorder extension in this tab; a cloud call runs
 * in a remote browser, so it is read from GET /api/calls/:id every 2 s until
 * the call is over. Resets whenever `callId` changes, so a stale phase from a
 * previous call never leaks onto a new one.
 */
export function useLiveCallState(callId: string | null): LiveCallState {
  const [phase, setPhase] = useState<CloudCallPhase | null>(null);
  const [cloud, setCloud] = useState<LiveCallState["cloud"]>(null);

  useEffect(() => {
    setPhase(null);
    setCloud(null);
    if (!callId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const unsubscribe = subscribeToCallUpdates((update) => {
      if (update.callId === callId) setPhase(update.phase);
    });

    const poll = async (first: boolean) => {
      let call: CallDetail | null = null;
      try {
        call = await getCall(callId);
      } catch {
        // A blip; a cloud call is tried again below, anything else is left to the bridge.
      }
      if (cancelled) return;
      if (call?.mode === "agent_cloud") {
        setCloud({ stationName: call.stationName ?? null, remoteRep: !!call.remoteRep });
        const next = terminalPhase(call);
        if (next) setPhase(next);
        // Over once the call has ended and its transcript has settled (see the server's settledLivePhase).
        if (TERMINAL_CALL_STATUSES.includes(call.status) && call.transcriptStatus !== "pending") return;
      } else if (call || !first) {
        return;
      }
      timer = setTimeout(() => void poll(false), CLOUD_POLL_MS);
    };
    void poll(true);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      unsubscribe();
    };
  }, [callId]);

  return { phase, cloud };
}

/**
 * The latest phase for `callId` in this tab, or null before any update
 * arrives (or when `callId` is null): pushed by the extension for a rep's
 * call, polled from the server for a cloud one.
 */
export function useLiveCall(callId: string | null): CloudCallPhase | null {
  return useLiveCallState(callId).phase;
}

/** Whichever call, by id, most recently pushed a phase update in this tab. */
export type LatestLiveCall = { callId: string; phase: RecorderCallPhase };

/**
 * The most recently updated call in this tab, id included. A caller may not
 * yet know which call id to watch — e.g. a panel opened before its first
 * poll has resolved the contact's calls — so this bridges that gap: whatever
 * call the extension is actively reporting on, whoever placed it.
 */
export function useLatestLiveCall(): LatestLiveCall | null {
  const [latest, setLatest] = useState<LatestLiveCall | null>(null);

  useEffect(() => {
    return subscribeToCallUpdates((update) => {
      setLatest({ callId: update.callId, phase: update.phase });
    });
  }, []);

  return latest;
}
