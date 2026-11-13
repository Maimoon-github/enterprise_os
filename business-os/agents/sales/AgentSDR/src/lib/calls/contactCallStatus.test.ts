import { describe, expect, test } from "bun:test";
import { contactCallStatusForCall, nextContactCallState, type ContactCallState } from "./contactCallStatus";

const NOW = new Date("2026-09-30T10:00:00Z");
const DAY = 24 * 60 * 60 * 1000;
const fresh: ContactCallState = { callStatus: "calling", stage: "to_call", unansweredAttempts: 0, followUpAt: null };

describe("nextContactCallState — the retry schedule", () => {
  test("unanswered calls come due again after 1, 2, then 4 days", () => {
    const first = nextContactCallState(fresh, "no_answer", NOW);
    expect(first).toEqual({ callStatus: "no_answer", stage: "to_call", unansweredAttempts: 1, followUpAt: new Date(NOW.getTime() + DAY) });
    const second = nextContactCallState({ ...first, callStatus: "calling" }, "busy", NOW);
    expect(second.unansweredAttempts).toBe(2);
    expect(second.followUpAt).toEqual(new Date(NOW.getTime() + 2 * DAY));
    const third = nextContactCallState({ ...second, callStatus: "calling" }, "no_answer", NOW);
    expect(third.followUpAt).toEqual(new Date(NOW.getTime() + 4 * DAY));
    expect(third.stage).toBe("to_call");
  });

  test("the fourth unanswered call in a row finishes the lead", () => {
    const state = nextContactCallState({ ...fresh, unansweredAttempts: 3 }, "no_answer", NOW);
    expect(state).toEqual({ callStatus: "no_answer", stage: "done", unansweredAttempts: 4, followUpAt: null });
  });

  test("a lead in Follow-up stays there while it is retried", () => {
    const state = nextContactCallState({ ...fresh, stage: "follow_up" }, "no_answer", NOW);
    expect(state.stage).toBe("follow_up");
  });

  test("connecting resets the count and moves the lead to Follow-up", () => {
    const state = nextContactCallState({ ...fresh, unansweredAttempts: 2, followUpAt: NOW }, "connected", NOW);
    expect(state).toEqual({ callStatus: "connected", stage: "follow_up", unansweredAttempts: 0, followUpAt: null });
  });

  test("not on WhatsApp and wrong number finish the lead", () => {
    expect(nextContactCallState(fresh, "not_on_whatsapp", NOW).stage).toBe("done");
    expect(nextContactCallState(fresh, "wrong_number", NOW).stage).toBe("done");
  });

  test("a failed call changes only the status", () => {
    const current = { ...fresh, unansweredAttempts: 1, followUpAt: NOW };
    expect(nextContactCallState(current, "failed", NOW)).toEqual({ ...current, callStatus: "failed" });
  });

  test("a rep relabelling no answer as busy does not count a second attempt", () => {
    const current: ContactCallState = { callStatus: "no_answer", stage: "to_call", unansweredAttempts: 1, followUpAt: NOW };
    expect(nextContactCallState(current, "busy", NOW, { manual: true })).toEqual({ ...current, callStatus: "busy" });
  });

  test("a rep marking a connected call as busy does count one", () => {
    const current: ContactCallState = { callStatus: "connected", stage: "follow_up", unansweredAttempts: 0, followUpAt: null };
    expect(nextContactCallState(current, "busy", NOW, { manual: true }).unansweredAttempts).toBe(1);
  });
});

describe("contactCallStatusForCall", () => {
  test("maps each way a call ends", () => {
    expect(contactCallStatusForCall({ status: "pending", error: null })).toBe("calling");
    expect(contactCallStatusForCall({ status: "recorded", error: null })).toBe("connected");
    expect(contactCallStatusForCall({ status: "no_recording", error: "Cancelled" })).toBe("no_answer");
    expect(contactCallStatusForCall({ status: "failed", error: "This number isn't on WhatsApp" })).toBe("not_on_whatsapp");
    expect(
      contactCallStatusForCall({
        status: "failed",
        error: "This number isn't on WhatsApp for calls (its chat has no Voice call button, as with a business number)",
      }),
    ).toBe("not_on_whatsapp");
    expect(contactCallStatusForCall({ status: "failed", error: "Upload failed: network" })).toBe("connected");
    expect(contactCallStatusForCall({ status: "failed", error: "Recording failed: no mic" })).toBe("failed");
  });
});
