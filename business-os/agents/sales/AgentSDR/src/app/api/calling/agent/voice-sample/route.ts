import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import { voiceSample } from "@/lib/calls/liveAgent";
import { callApiErrorResponse } from "@/lib/calls/sessions";

/**
 * GET /api/calling/agent/voice-sample?voice=Kore&name=Riya — a few seconds of
 * that voice saying a typical opening, as a WAV, spoken by the same Live model
 * the calls use (the ▶ beside the voice picker). Kept in memory per voice and
 * name, so only the first play of each waits for Gemini.
 */
export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      const params = request.nextUrl.searchParams;
      const wav = await voiceSample(params.get("voice"), params.get("name"));
      return new Response(wav, {
        headers: { "Content-Type": "audio/wav", "Content-Length": String(wav.byteLength), "Cache-Control": "private, max-age=86400" },
      });
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
