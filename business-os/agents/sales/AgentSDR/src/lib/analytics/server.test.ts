import { describe, expect, test } from "bun:test";
import { createLimiter } from "./server";

const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 1));

describe("createLimiter", () => {
  test("never has more than `limit` tasks in flight, across callers sharing it", async () => {
    const limit = createLimiter(3);
    let active = 0;
    let peak = 0;
    const task = (value: number) => async () => {
      active += 1;
      peak = Math.max(peak, active);
      await tick();
      active -= 1;
      return value;
    };
    // Two "loaders" fanning out through the same limiter at once.
    const [a, b] = await Promise.all([
      Promise.all([1, 2, 3, 4, 5].map((n) => limit(task(n)))),
      Promise.all([6, 7, 8, 9].map((n) => limit(task(n)))),
    ]);
    expect(a).toEqual([1, 2, 3, 4, 5]);
    expect(b).toEqual([6, 7, 8, 9]);
    expect(peak).toBe(3);
  });

  test("a failing task frees its slot and rejects only its own caller", async () => {
    const limit = createLimiter(1);
    const failed = limit(async () => {
      throw new Error("boom");
    });
    const next = limit(async () => "ok");
    await expect(failed).rejects.toThrow("boom");
    expect(await next).toBe("ok");
  });
});
