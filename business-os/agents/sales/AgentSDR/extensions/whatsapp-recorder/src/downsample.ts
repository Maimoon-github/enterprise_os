/**
 * Streaming downsampler for the lead's side of an AI-agent call: the audio
 * context's rate (48 kHz on a Mac, 44.1 kHz on the Linux call worker) to the
 * 16 kHz Gemini Live takes.
 *
 * It replaced picking the nearest sample per ScriptProcessor block, which had
 * no low-pass filter, restarted at every block (a glitch every 85 ms) and ran
 * 0.5–1% fast — about 18 dB signal-to-distortion. Gemini heard the lead as
 * unclear ("I didn't quite catch that", "I don't speak Spanish") and kept
 * stopping to listen on the server (23 Oct 2026). This one low-passes with a
 * windowed sinc below the output's Nyquist and carries its history and
 * fractional position from block to block, so the output is one continuous
 * signal at exactly the output rate.
 */

const HALF_TAPS = 16;
/** Pass band edge as a share of the output Nyquist frequency (16 kHz → 7.2 kHz). */
const PASS = 0.9;

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
