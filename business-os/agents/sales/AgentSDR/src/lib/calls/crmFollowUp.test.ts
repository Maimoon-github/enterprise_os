import { describe, expect, test } from "bun:test";
import { callFollowUpUpdate, type FollowUpRecordState } from "./crmFollowUp";

const DUE = new Date("2026-10-02T09:00:00Z");
const idle: FollowUpRecordState = { workflowState: "idle", nextActionAt: null, activeChannel: null, latestInboundMessageId: null };

describe("callFollowUpUpdate", () => {
  test("a due follow-up puts a call-only record in waiting, on WhatsApp, until the date", () => {
    expect(callFollowUpUpdate(idle, DUE)).toEqual({ workflowState: "waiting", nextActionAt: DUE, activeChannel: "whatsapp" });
  });

  test("a new date moves a waiting record; the same date is left alone", () => {
    const waiting: FollowUpRecordState = { ...idle, workflowState: "waiting", nextActionAt: DUE, activeChannel: "whatsapp" };
    expect(callFollowUpUpdate(waiting, new Date(DUE))).toBeNull();
    const later = new Date("2026-10-05T09:00:00Z");
    expect(callFollowUpUpdate(waiting, later)).toEqual({ workflowState: "waiting", nextActionAt: later, activeChannel: "whatsapp" });
  });

  test("no follow-up any more sends a waiting record back to idle", () => {
    const waiting: FollowUpRecordState = { ...idle, workflowState: "waiting", nextActionAt: DUE, activeChannel: "whatsapp" };
    expect(callFollowUpUpdate(waiting, null)).toEqual({ workflowState: "idle", nextActionAt: null, activeChannel: "whatsapp" });
    expect(callFollowUpUpdate(idle, null)).toBeNull();
  });

  test("a lead with an email or LinkedIn thread is left to its sequence", () => {
    expect(callFollowUpUpdate({ ...idle, latestInboundMessageId: "msg" }, DUE)).toBeNull();
    expect(callFollowUpUpdate({ ...idle, activeChannel: "email" }, DUE)).toBeNull();
    expect(callFollowUpUpdate({ ...idle, activeChannel: "linkedin", workflowState: "waiting" }, null)).toBeNull();
  });

  test("a record that needs a person for something else, or is paused or closed, keeps its state", () => {
    for (const workflowState of ["action_required", "error", "paused", "closed"] as const) {
      expect(callFollowUpUpdate({ ...idle, workflowState }, DUE)).toBeNull();
    }
  });
});
