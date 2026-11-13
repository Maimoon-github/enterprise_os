import type { NextRequest } from "next/server";
import { MAX_HEARD_AUDIO_BYTES } from "@/lib/calls/contract";
import { saveHeardAudio } from "@/lib/calls/liveAgent";
import { CallApiError, callApiErrorResponse, withRecorderScope } from "@/lib/calls/sessions";
import { heardAudioKeyFor, putRecordingObject } from "@/lib/calls/storage";

/**
 * Test option (AGENT_SAVE_HEARD_AUDIO=true): the extension uploads exactly
 * what the AI agent heard on this call — the lead's side as sent to the model,
 * 16 kHz mono WAV — after the call. Bearer-token authorized like the rest of
 * this prefix; accepted after the call has finished, since it is sent last.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withRecorderScope(request, (await params).id, async (row) => {
      if (!saveHeardAudio()) throw new CallApiError(404, "Saving what the agent heard is off on this server");
      const body = new Uint8Array(await request.arrayBuffer());
      if (body.byteLength > MAX_HEARD_AUDIO_BYTES) throw new CallApiError(413, "The heard audio is too large");
      if (body.byteLength < 44 || String.fromCharCode(...body.subarray(0, 4)) !== "RIFF") {
        throw new CallApiError(400, "Expected a WAV file");
      }
      const key = heardAudioKeyFor(row.id, row.createdAt);
      await putRecordingObject(key, body, "audio/wav");
      return Response.json({ ok: true, bytes: body.byteLength });
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
