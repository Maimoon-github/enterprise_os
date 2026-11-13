import { describe, expect, test } from "bun:test";
import { RepRelay, parseRelayLines, pcmFromBase64 } from "./rep-relay";

const base64Of = (samples: number[]) => Buffer.from(new Int16Array(samples).buffer).toString("base64");

describe("parseRelayLines", () => {
  test("parses complete lines and keeps the partial one", () => {
    const { events, rest } = parseRelayLines('{"t":"ping"}\n{"t":"peer","present":true}\n{"t":"au');
    expect(events).toEqual([{ t: "ping" }, { t: "peer", present: true }]);
    expect(rest).toBe('{"t":"au');
    expect(parseRelayLines(`${rest}dio","pcm":"AAA="}\n`).events).toEqual([{ t: "audio", pcm: "AAA=" }]);
  });

  test("skips blank lines, bad JSON and unknown or malformed events", () => {
    const text = '\n  \nnot json\n{"t":"dance"}\n{"t":"audio"}\n{"t":"peer","present":"yes"}\n[1]\nnull\n{"t":"hangup"}\r\n{"t":"uplink"}\n';
    expect(parseRelayLines(text)).toEqual({ events: [{ t: "hangup" }, { t: "uplink" }], rest: "" });
  });
});

describe("pcmFromBase64", () => {
  test("round-trips 16-bit samples", () => {
    const samples = [0, 1, -1, 32767, -32768, 1234];
    expect(Array.from(new Int16Array(pcmFromBase64(base64Of(samples))))).toEqual(samples);
  });

  test("drops an odd trailing byte", () => {
    const odd = Buffer.from([1, 0, 2, 0, 9]).toString("base64");
    expect(Array.from(new Int16Array(pcmFromBase64(odd)))).toEqual([1, 2]);
  });
});

/** A response whose body yields `chunks` (strings), then ends. */
function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    }),
  );
}

describe("RepRelay", () => {
  test("plays the rep's audio and hangs up on the rep's hang-up", async () => {
    const played: number[][] = [];
    const hangups: string[] = [];
    const requests: RequestInit[] = [];
    const relay = new RepRelay({
      url: "https://app.example/api/call-recorder/calls/c1/relay",
      token: "tok",
      play: (pcm) => played.push(Array.from(new Int16Array(pcm))),
      hangup: (why) => hangups.push(why),
      trace: () => {},
      canStream: false,
      fetch: async (_url, init) => {
        requests.push(init);
        const audio = JSON.stringify({ t: "audio", pcm: base64Of([7, 8]) });
        // An event split across reads, as a network delivers it.
        return streamResponse([`{"t":"peer","present":true}\n${audio.slice(0, 9)}`, `${audio.slice(9)}\n{"t":"hangup"}\n`]);
      },
    });
    relay.start();
    await waitFor(() => hangups.length > 0);
    expect(played).toEqual([[7, 8]]);
    expect(hangups).toEqual(["the rep hung up"]);
    expect(requests).toHaveLength(1);
    expect((requests[0].headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  test("a refused stream hangs up without retrying", async () => {
    const hangups: string[] = [];
    let calls = 0;
    const relay = new RepRelay({
      url: "u",
      token: "t",
      play: () => {},
      hangup: (why) => hangups.push(why),
      trace: () => {},
      canStream: false,
      fetch: async () => {
        calls += 1;
        return new Response("gone", { status: 410 });
      },
    });
    relay.start();
    await waitFor(() => hangups.length > 0);
    expect(hangups[0]).toContain("410");
    expect(calls).toBe(1);
  });

  test("where streaming is not possible, sends the lead's audio in batches, one request in flight", async () => {
    const bodies: number[][] = [];
    const gate = { release: () => {} };
    const relay = new RepRelay({
      url: "u",
      token: "t",
      play: () => {},
      hangup: () => {},
      trace: () => {},
      canStream: false,
      fetch: async (_url, init) => {
        const bytes = init.body as Uint8Array;
        bodies.push(Array.from(new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2)));
        await new Promise<void>((resolve) => (gate.release = resolve));
        return new Response(null, { status: 204 });
      },
    });
    // 40 ms at 16 kHz is 640 samples: less than that waits for more.
    relay.sendLead(new Int16Array(600).fill(1).buffer);
    expect(bodies).toHaveLength(0);
    relay.sendLead(new Int16Array(100).fill(2).buffer);
    await waitFor(() => bodies.length === 1);
    expect(bodies[0]).toHaveLength(700);
    // While that request is out, more queues up and goes as one.
    relay.sendLead(new Int16Array(400).fill(3).buffer);
    relay.sendLead(new Int16Array(400).fill(4).buffer);
    expect(bodies).toHaveLength(1);
    gate.release();
    await waitFor(() => bodies.length === 2);
    expect(bodies[1]).toHaveLength(800);
    gate.release();
    relay.close();
  });
});

async function waitFor(condition: () => boolean, timeoutMs = 1_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (!condition()) {
    if (Date.now() > deadline) throw new Error("timed out");
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
}
