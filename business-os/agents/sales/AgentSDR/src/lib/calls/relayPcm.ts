/**
 * The rep's tab's audio arithmetic for the relay (contract.ts, "a rep talking
 * through a calling station"): the microphone down to mono 16-bit LE PCM at
 * REP_RELAY_SAMPLE_RATE, what to send next, and when to play what arrives.
 * Pure and client-safe, so it is tested without a browser.
 */

import { REP_RELAY_MAX_CHUNK_MS, REP_RELAY_SAMPLE_RATE } from "./contract";

const HALF_TAPS = 16;
/** Pass band edge as a share of the output Nyquist frequency (16 kHz → 7.2 kHz). */
const PASS = 0.9;

/**
 * Streaming downsampler: the audio context's rate (48 kHz on most machines)
 * to `outputRate`. A windowed-sinc low-pass below the output's Nyquist, with
 * its history and fractional position carried from block to block, so the
 * output is one continuous signal at exactly the output rate. The same
 * approach as the recorder extension's downsample.ts, which replaced
 * nearest-sample picking that Gemini heard as unclear (23 Oct 2026); copied
 * rather than imported, since the extension is its own package.
 */
export function createDownsampler(inputRate: number, outputRate: number): (block: Float32Array) => Int16Array<ArrayBuffer> {
  const step = inputRate / outputRate;
  // Low-pass at PASS × the output Nyquist, in cycles per input sample (×2).
  const cutoff = Math.min(1, PASS / step);
  let history = new Float32Array(HALF_TAPS);
  let position = HALF_TAPS;

  return (block) => {
    const buffer = new Float32Array(history.length + block.length);
    buffer.set(history);
    buffer.set(block, history.length);
    const out: number[] = [];
    while (position + HALF_TAPS < buffer.length) {
      const center = Math.floor(position);
      const fraction = position - center;
      let sum = 0;
      let weights = 0;
      for (let k = -HALF_TAPS + 1; k <= HALF_TAPS; k++) {
        const x = k - fraction;
        const window = 0.5 + 0.5 * Math.cos((Math.PI * x) / HALF_TAPS);
        const arg = Math.PI * cutoff * x;
        const weight = (arg === 0 ? 1 : Math.sin(arg) / arg) * window;
        sum += buffer[center + k]! * weight;
        weights += weight;
      }
      out.push(sum / weights);
      position += step;
    }
    // Keep what the next block's first outputs still reach back to.
    const keepFrom = Math.max(0, Math.floor(position) - HALF_TAPS);
    history = buffer.slice(keepFrom);
    position -= keepFrom;

    const pcm = new Int16Array(out.length);
    for (let i = 0; i < out.length; i++) pcm[i] = Math.max(-1, Math.min(1, out[i]!)) * 0x7fff;
    return pcm;
  };
}

/** Samples to little-endian bytes, whatever the machine's own byte order. */
export function int16ToLeBytes(pcm: Int16Array): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(pcm.length * 2);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < pcm.length; i++) view.setInt16(i * 2, pcm[i]!, true);
  return bytes;
}

/** Little-endian 16-bit PCM bytes to samples in [-1, 1), for an AudioBuffer. A stray odd byte is ignored. */
export function leBytesToFloat32(bytes: Uint8Array): Float32Array<ArrayBuffer> {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const out = new Float32Array(bytes.byteLength >> 1);
  for (let i = 0; i < out.length; i++) out[i] = view.getInt16(i * 2, true) / 0x8000;
  return out;
}

export function base64ToBytes(base64: string): Uint8Array<ArrayBuffer> {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/** Most samples one POST carries, and most the outbox holds: REP_RELAY_MAX_CHUNK_MS. */
export const MAX_OUTBOX_SAMPLES = (REP_RELAY_SAMPLE_RATE * REP_RELAY_MAX_CHUNK_MS) / 1000;

/**
 * PCM waiting to go up (relayUplink.ts). The sender takes everything at once
 * (the stream's next read, or the next POST); while the network is stuck,
 * the oldest audio is dropped so the backlog never passes
 * REP_RELAY_MAX_CHUNK_MS — late speech is worse than a gap.
 */
export class PcmOutbox {
  private blocks: Int16Array[] = [];
  private samples = 0;

  constructor(private readonly maxSamples = MAX_OUTBOX_SAMPLES) {}

  get size(): number {
    return this.samples;
  }

  /** Queues `pcm`; returns how many samples were dropped to stay within the cap. */
  push(pcm: Int16Array): number {
    if (!pcm.length) return 0;
    this.blocks.push(pcm);
    this.samples += pcm.length;
    let dropped = 0;
    while (this.samples > this.maxSamples) {
      const oldest = this.blocks[0]!;
      const excess = this.samples - this.maxSamples;
      if (oldest.length <= excess) {
        this.blocks.shift();
        this.samples -= oldest.length;
        dropped += oldest.length;
      } else {
        this.blocks[0] = oldest.subarray(excess);
        this.samples -= excess;
        dropped += excess;
      }
    }
    return dropped;
  }

  /** Everything waiting, as LE bytes; null when empty. */
  take(): Uint8Array<ArrayBuffer> | null {
    if (!this.samples) return null;
    const all = new Int16Array(this.samples);
    let offset = 0;
    for (const block of this.blocks) {
      all.set(block, offset);
      offset += block.length;
    }
    this.clear();
    return int16ToLeBytes(all);
  }

  clear(): void {
    this.blocks = [];
    this.samples = 0;
  }
}

/**
 * When to start playing a chunk that just arrived (seconds, the audio
 * context's clock): right after what is queued; after `jitterS` of buffering
 * when nothing is (the start, or after running dry); or null — drop it —
 * when more than `maxBufferS` is already queued, to catch up after a stall.
 */
export function nextPlayTime(now: number, playhead: number, jitterS: number, maxBufferS: number): number | null {
  if (playhead <= now) return now + jitterS;
  if (playhead - now > maxBufferS) return null;
  return playhead;
}
