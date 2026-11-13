"use client";

import { RiVolumeMuteLine } from "@remixicon/react";
import { useDemoMode } from "@/components/demo/DemoProvider";

/**
 * A call's recording, starting at the pick-up. Recordings begin when the call
 * opens the microphone, so they open with the ringing before the lead
 * answered (recordingOffsetMs); the player skips it once the audio loads.
 * The rep can still scrub back to hear it.
 */
export function RecordingPlayer({ callId, offsetMs }: { callId: string; offsetMs: number | null }) {
  const demo = useDemoMode();
  const start = offsetMs && offsetMs > 0 ? offsetMs / 1000 : 0;
  // The demo's calls are fictional: there is a transcript, but no audio.
  if (demo) {
    return (
      <p className="flex items-center gap-2 rounded-lg bg-bg-weak-50 px-3 py-2 text-paragraph-xs text-text-sub-600">
        <RiVolumeMuteLine className="size-4 shrink-0 text-text-soft-400" />
        Recordings don&apos;t play in the demo; the call&apos;s transcript and summary still show.
      </p>
    );
  }
  return (
    <audio
      controls
      preload="none"
      src={`/api/calls/${callId}/recording`}
      className="w-full"
      onLoadedMetadata={(event) => {
        if (start > 0 && event.currentTarget.currentTime < start) event.currentTarget.currentTime = start;
      }}
    />
  );
}
