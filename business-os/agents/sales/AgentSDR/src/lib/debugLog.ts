/**
 * Reusable step-by-step processing logger for pipelines we need to debug in
 * production (webhook handlers, background jobs, ...). Accumulates
 * timestamped log lines in memory as the pipeline runs, then hands back a
 * plain array + status you can persist with an inbound diagnostic event
 * and render as a "Processing Log" panel.
 *
 * Not tied to any table — any pipeline can create one, log through it, and
 * persist `logger.steps` / `logger.status` wherever makes sense for it.
 */

export type StepLogLevel = "info" | "warn" | "error";

export type StepLogEntry = {
  ts: string;
  level: StepLogLevel;
  message: string;
};

export type StepLogStatus = "ok" | "skipped" | "error";

export interface StepLogger {
  info(message: string): void;
  warn(message: string): void;
  error(message: string): void;
  /** Marks the run's outcome. Call once, right before returning. */
  finish(status: StepLogStatus): void;
  readonly steps: StepLogEntry[];
  readonly status: StepLogStatus;
}

/** Create a fresh logger. `initialStatus` defaults to "ok" until `finish()` overrides it. */
export function createStepLogger(): StepLogger {
  const steps: StepLogEntry[] = [];
  let status: StepLogStatus = "ok";

  function push(level: StepLogLevel, message: string) {
    steps.push({ ts: new Date().toISOString(), level, message });
  }

  return {
    info: (message) => push("info", message),
    warn: (message) => push("warn", message),
    error: (message) => push("error", message),
    finish: (next) => {
      status = next;
    },
    get steps() {
      return steps;
    },
    get status() {
      return status;
    },
  };
}
