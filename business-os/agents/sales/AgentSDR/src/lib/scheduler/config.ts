import { isDemoMode } from "@/lib/demo/mode";

type Environment = Record<string, string | undefined>;

const OFF = new Set(["0", "false", "no", "off"]);

/**
 * Whether this process runs the scheduled jobs itself (internalScheduler.ts).
 * Production only (a dev server's hot reloads would start duplicate loops),
 * never in the read-only demo, and `INTERNAL_SCHEDULER=false` turns it off
 * for deployments that keep an external cron instead.
 *
 * The job endpoints dedupe scheduled calls against the slot claims only when
 * this is true: with the scheduler off, an external cron gets exactly the
 * old behaviour.
 */
export function internalSchedulerEnabled(env: Environment = process.env): boolean {
  if (env.NODE_ENV !== "production") return false;
  if (isDemoMode(env)) return false;
  return !OFF.has(env.INTERNAL_SCHEDULER?.trim().toLowerCase() ?? "");
}
