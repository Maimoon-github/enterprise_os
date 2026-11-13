import { describe, expect, test } from "bun:test";
import { INCOMING_CALL_MAX_AGE_MS, type StationIncomingCall } from "../../../src/lib/calls/stationContract";
import { addIncoming, asIncomingCall, endIncoming, INCOMING_KEEP_MS, isAcceptLabel, maskDigits, phoneFromScreenText, takeIncoming, type IncomingEntry } from "./incoming";

const NOW = 1_800_000_000_000;
const ring = (waCallId: string, ageMs = 1_000, phone: string | null = "+911111111111"): StationIncomingCall => ({
  waCallId,
  phone,
  callerName: null,
  isVideo: false,
  isGroup: false,
  at: NOW - ageMs,
});

describe("asIncomingCall", () => {
  test("keeps a well-formed ring and drops a malformed number", () => {
    expect(asIncomingCall({ ...ring("w1"), callerName: "  Asha " })).toEqual({ ...ring("w1"), callerName: "Asha" });
    expect(asIncomingCall({ ...ring("w1"), phone: "911111111111" })?.phone).toBeNull();
  });
  test("refuses anything without an id or a time", () => {
    for (const bad of [null, "x", { waCallId: "", at: NOW }, { waCallId: "w1" }, { waCallId: "w1", at: Number.NaN }]) {
      expect(asIncomingCall(bad)).toBeNull();
    }
  });
});

describe("the ring list", () => {
  test("adds a ring once; a repeat fills in the number the first lacked", () => {
    let list: IncomingEntry[] = [];
    let added: boolean;
    ({ list, added } = addIncoming(list, ring("w1", 1_000, null), 7, NOW));
    expect(added).toBe(true);
    ({ list, added } = addIncoming(list, ring("w1"), 7, NOW));
    expect(added).toBe(false);
    expect(list).toEqual([{ call: ring("w1"), tabId: 7, taken: false }]);
  });

  test("takes fresh rings once, oldest first, and keeps them for answerCall to find", () => {
    let list: IncomingEntry[] = [];
    list = addIncoming(list, ring("late", 1_000), 1, NOW).list;
    list = addIncoming(list, ring("early", 5_000), 1, NOW).list;
    list = addIncoming(list, ring("stale", INCOMING_CALL_MAX_AGE_MS + 1), 1, NOW).list;
    const first = takeIncoming(list, NOW);
    expect(first.taken.map((c) => c.waCallId)).toEqual(["early", "late"]);
    expect(first.list.map((e) => e.call.waCallId)).toEqual(["late", "early", "stale"]);
    expect(takeIncoming(first.list, NOW).taken).toEqual([]);
  });

  test("forgets old rings and ended ones", () => {
    let list = addIncoming([], ring("w1"), 1, NOW).list;
    list = addIncoming(list, ring("w2"), 1, NOW).list;
    expect(endIncoming(list, "w1").map((e) => e.call.waCallId)).toEqual(["w2"]);
    expect(takeIncoming(list, NOW + INCOMING_KEEP_MS).list).toEqual([]);
    expect(addIncoming([], ring("w3", INCOMING_KEEP_MS), 1, NOW).added).toBe(false);
  });
});

describe("isAcceptLabel", () => {
  test("matches WhatsApp's answer controls and never Decline", () => {
    for (const ok of ["Accept", "accept call", "Answer", "Accept voice call", " Answer video call "]) expect(isAcceptLabel(ok)).toBe(true);
    for (const no of ["Decline", "Decline call", "Accept and decline", "Voice call", "", null, "Accepted"]) expect(isAcceptLabel(no)).toBe(false);
  });
  test("masks digits for the log", () => {
    expect(maskDigits("Call +91 98765")).toBe("Call +## #####");
  });
});

describe("phoneFromScreenText", () => {
  test("reads a number shown on the call screen", () => {
    expect(phoneFromScreenText("+91 96000 00001 WhatsApp voice call Decline Accept")).toBe("+919600000001");
    expect(phoneFromScreenText("Incoming call from +1 (415) 555-0100")).toBe("+14155550100");
  });
  test("a saved name, a time or a count is not a number", () => {
    expect(phoneFromScreenText("Pulkit WhatsApp voice call")).toBeNull();
    expect(phoneFromScreenText("12:45 3 missed calls")).toBeNull();
    expect(phoneFromScreenText(null)).toBeNull();
  });
});
