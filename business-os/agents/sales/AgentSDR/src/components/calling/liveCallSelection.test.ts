import { describe, expect, test } from "bun:test";
import { selectLiveCallId } from "./liveCallSelection";

const NOW = Date.parse("2026-09-29T12:00:00.000Z");

describe("selectLiveCallId", () => {
  test("prefers the contact's own call while it's in flight", () => {
    const id = selectLiveCallId({
      latestCall: { id: "call-1", status: "in_progress", createdAt: "2026-09-01T00:00:00.000Z" },
      callIds: ["call-1"],
      latestLiveCallId: "call-9",
      now: NOW,
    });
    expect(id).toBe("call-1");
  });

  test("prefers the contact's own call when it was just placed, even if terminal", () => {
    const id = selectLiveCallId({
      latestCall: { id: "call-1", status: "recorded", createdAt: new Date(NOW - 60_000).toISOString() },
      callIds: ["call-1"],
      latestLiveCallId: null,
      now: NOW,
    });
    expect(id).toBe("call-1");
  });

  test("an old, terminal call of the contact's own is not selected", () => {
    const id = selectLiveCallId({
      latestCall: { id: "call-1", status: "recorded", createdAt: new Date(NOW - 20 * 60_000).toISOString() },
      callIds: ["call-1"],
      latestLiveCallId: null,
      now: NOW,
    });
    expect(id).toBeNull();
  });

  test("falls back to the latest live update when it matches one of the contact's loaded calls", () => {
    const id = selectLiveCallId({
      latestCall: { id: "call-1", status: "recorded", createdAt: new Date(NOW - 20 * 60_000).toISOString() },
      callIds: ["call-1", "call-2"],
      latestLiveCallId: "call-2",
      now: NOW,
    });
    expect(id).toBe("call-2");
  });

  test("falls back to the latest live update when the contact has no calls loaded yet", () => {
    const id = selectLiveCallId({
      latestCall: null,
      callIds: [],
      latestLiveCallId: "call-7",
      now: NOW,
    });
    expect(id).toBe("call-7");
  });

  test("ignores a live update that belongs to a different, already-loaded contact", () => {
    const id = selectLiveCallId({
      latestCall: { id: "call-1", status: "recorded", createdAt: new Date(NOW - 20 * 60_000).toISOString() },
      callIds: ["call-1"],
      latestLiveCallId: "call-somewhere-else",
      now: NOW,
    });
    expect(id).toBeNull();
  });

  test("no calls and no live update means nothing to watch", () => {
    expect(selectLiveCallId({ latestCall: null, callIds: [], latestLiveCallId: null, now: NOW })).toBeNull();
  });
});
