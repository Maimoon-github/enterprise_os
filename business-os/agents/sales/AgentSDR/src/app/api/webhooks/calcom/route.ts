import { handleCalcomWebhook } from "@/lib/calls/aiCampaigns/booking";

/**
 * POST /api/webhooks/calcom?org=<organization id> — Cal.com's booking
 * webhook for AI calling campaigns. Public in proxy.ts: it authenticates
 * itself with the organization's webhook secret (x-cal-signature-256).
 * Ignored events answer 200; a bad signature 401.
 */
export async function POST(request: Request) {
  try {
    return await handleCalcomWebhook(request);
  } catch (error) {
    console.error("[webhooks/calcom] delivery failed:", error);
    return Response.json({ error: "Could not process the booking" }, { status: 500 });
  }
}
