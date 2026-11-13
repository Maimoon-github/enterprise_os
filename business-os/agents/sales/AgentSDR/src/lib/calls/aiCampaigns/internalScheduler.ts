/**
 * In-process tick for AI calling campaigns, started from instrumentation.ts
 * in production only, like the WhatsApp campaign sender: a dev server shares
 * the production database, and although every step is claimed by a unique
 * row (and a number by its next_call_at) two ticking processes would still
 * compete for numbers. Overlapping ticks are skipped and errors are logged,
 * never thrown. PAUSE_AI_CALLING stops it (engine.ts).
 */
import { runAiCallingTick } from "./engine";

const TICK_INTERVAL_MS = Number(process.env.AI_CALLING_TICK_INTERVAL_MS ?? 20_000);

let started = false;
let tickRunning = false;
let tickCount = 0;

async function safeTick() {
  if (tickRunning) {
    console.warn("[calls/aiCampaigns/internalScheduler] previous tick still running — skipping this cycle");
    return;
  }
  tickRunning = true;
  try {
    const result = await runAiCallingTick();
    tickCount += 1;
    if (tickCount % 30 === 0 || result.calls > 0 || result.messages > 0 || result.settled > 0 || result.failed > 0) {
      console.log(`[calls/aiCampaigns/internalScheduler] tick #${tickCount}:`, result);
    }
  } catch (err) {
    console.error("[calls/aiCampaigns/internalScheduler] tick threw:", err);
  } finally {
    tickRunning = false;
  }
}

/** Idempotent: only the first call starts the loop. */
export function startInternalAiCallingScheduler() {
  if (started) return;
  started = true;
  const interval = Number.isFinite(TICK_INTERVAL_MS) && TICK_INTERVAL_MS >= 5_000 ? TICK_INTERVAL_MS : 20_000;
  console.log(`[calls/aiCampaigns/internalScheduler] starting — tick every ${interval}ms`);
  setInterval(safeTick, interval);
  setTimeout(safeTick, 11_000);
}
