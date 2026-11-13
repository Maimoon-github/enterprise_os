import { describe, expect, test } from "bun:test";
import { createDownsampler } from "./downsample";

const OUT = 16_000;
const BLOCK = 4096;
const TONES = [220, 700, 1500, 3100, 6000];

/** Speech-band tones at `rate`, fed in ScriptProcessor-sized blocks, back as one 16 kHz signal. */
function run(rate: number, seconds: number): { y: Int16Array; fed: number } {
  const downsample = createDownsampler(rate, OUT);
  const parts: Int16Array[] = [];
  let fed = 0;
  for (let start = 0; start < rate * seconds; start += BLOCK) {
    fed += BLOCK;
    const block = new Float32Array(BLOCK);
    for (let i = 0; i < BLOCK; i++) for (const f of TONES) block[i]! += 0.15 * Math.sin((2 * Math.PI * f * (start + i)) / rate);
    parts.push(downsample(block));
  }
  const out = new Int16Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) {
    out.set(p, at);
    at += p.length;
  }
  return { y: out, fed };
}

/** Worst signal-to-distortion over 50 ms windows, fitting each tone's amplitude and phase per window. */
function worstSnrDb(y: Int16Array): number {
  const W = 800;
  let worst = Infinity;
  for (let w0 = 2_000; w0 + W < y.length - 2_000; w0 += W) {
    const fit = TONES.map((f) => {
      let s = 0;
      let c = 0;
      for (let i = w0; i < w0 + W; i++) {
        const t = (2 * Math.PI * f * i) / OUT;
        s += (y[i]! / 0x7fff) * Math.sin(t);
        c += (y[i]! / 0x7fff) * Math.cos(t);
      }
      return [(2 * s) / W, (2 * c) / W] as const;
    });
    let signal = 0;
    let error = 0;
    for (let i = w0; i < w0 + W; i++) {
      let ideal = 0;
      TONES.forEach((f, k) => {
        const t = (2 * Math.PI * f * i) / OUT;
        ideal += fit[k]![0] * Math.sin(t) + fit[k]![1] * Math.cos(t);
      });
      signal += ideal * ideal;
      error += (y[i]! / 0x7fff - ideal) ** 2;
    }
    worst = Math.min(worst, 10 * Math.log10(signal / error));
  }
  return worst;
}

describe("createDownsampler", () => {
  for (const rate of [44_100, 48_000]) {
    test(`${rate} Hz → 16 kHz: exact rate, clean across block edges`, () => {
      const { y, fed } = run(rate, 3);
      // One continuous signal: every input second gives 16 000 samples (less the filter's few-sample latency).
      expect(Math.abs(y.length - (fed * OUT) / rate)).toBeLessThan(20);
      // The old nearest-sample pick measured ~18 dB here.
      expect(worstSnrDb(y)).toBeGreaterThan(50);
    });
  }

  test("removes what 16 kHz cannot carry instead of folding it into speech", () => {
    const downsample = createDownsampler(48_000, OUT);
    const block = new Float32Array(BLOCK * 4);
    for (let i = 0; i < block.length; i++) block[i] = 0.5 * Math.sin((2 * Math.PI * 12_000 * i) / 48_000);
    const y = downsample(block);
    let energy = 0;
    for (let i = 200; i < y.length; i++) energy += (y[i]! / 0x7fff) ** 2;
    expect(10 * Math.log10(energy / (y.length - 200))).toBeLessThan(-40);
  });
});
