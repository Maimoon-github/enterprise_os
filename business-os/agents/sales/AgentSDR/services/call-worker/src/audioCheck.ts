/**
 * `npm run audio-check` — does this machine's browser run WhatsApp's 16 kHz
 * audio correctly? WhatsApp Web makes its call audio contexts with
 * `new AudioContext({ sampleRate: 16000 })`. CloakBrowser's free macOS build
 * (145) reports 48000 for them and renders at under a third of real time,
 * which garbles call audio both ways (23 Oct 2026); its Linux build is a
 * different one, so run this on the server before trusting it with calls.
 *
 * For each launcher it plays a 440 Hz tone in a 16 kHz context, carries it into
 * a default-rate context as a MediaStream (the path call audio takes), and
 * prints the rate reported, how fast the context's clock runs, and the tone's
 * signal-to-noise ratio on arrival. Healthy: reported 16000, clock 1.00x, SNR
 * well above 30 dB.
 */
import type { Browser } from "playwright-core";

const TEST = `(async () => {
  const a = new AudioContext({ sampleRate: 16000 });
  const osc = new OscillatorNode(a, { frequency: 440 });
  const bridge = a.createMediaStreamDestination();
  osc.connect(bridge);
  const b = new AudioContext();
  const sp = b.createScriptProcessor(4096, 1, 1);
  b.createMediaStreamSource(bridge.stream).connect(sp);
  sp.connect(b.createMediaStreamDestination());
  const snrs = [];
  sp.onaudioprocess = (e) => {
    const x = e.inputBuffer.getChannelData(0), sr = b.sampleRate;
    let s = 0, c = 0, p = 0;
    for (let i = 0; i < x.length; i++) { const t = 2 * Math.PI * 440 * i / sr; s += x[i] * Math.sin(t); c += x[i] * Math.cos(t); p += x[i] * x[i]; }
    if (p < 1e-6) return;
    const A = 2 * s / x.length, B = 2 * c / x.length;
    let r = 0;
    for (let i = 0; i < x.length; i++) { const t = 2 * Math.PI * 440 * i / sr; const d = x[i] - A * Math.sin(t) - B * Math.cos(t); r += d * d; }
    snrs.push(10 * Math.log10(p / Math.max(r, 1e-20)));
  };
  osc.start();
  const t0 = performance.now(), c0 = a.currentTime;
  await new Promise((r) => setTimeout(r, 3000));
  const secs = (performance.now() - t0) / 1000;
  const snr = snrs.length ? snrs.slice().sort((p, q) => p - q)[Math.floor(snrs.length / 2)] : null;
  const out = { reported: a.sampleRate, clock: (a.currentTime - c0) / secs, snr };
  await a.close(); await b.close();
  return out;
})()`;

type Result = { reported: number; clock: number; snr: number | null };

const headless = process.env.HEADLESS !== "false";
const args = ["--autoplay-policy=no-user-gesture-required"];

async function check(name: string, open: () => Promise<Browser>): Promise<boolean> {
  let browser: Browser | null = null;
  try {
    browser = await open();
    const page = await browser.newPage();
    await page.goto("https://example.com/");
    const r = (await page.evaluate(TEST)) as Result;
    const ok = r.reported === 16000 && Math.abs(r.clock - 1) < 0.1 && (r.snr ?? 0) > 30;
    console.log(
      `${name.padEnd(13)} ${ok ? "OK  " : "BAD "} reported ${r.reported} Hz, clock ${r.clock.toFixed(2)}x, ` +
        `SNR ${r.snr == null ? "no signal" : `${r.snr.toFixed(1)} dB`} — ${browser.version()}`,
    );
    return ok;
  } catch (e) {
    console.log(`${name.padEnd(13)} FAILED ${String(e).split("\n")[0]}`);
    return false;
  } finally {
    await browser?.close().catch(() => {});
  }
}

const results = [
  await check("cloak", async () => (await import("cloakbrowser")).launch({ headless, args })),
  await check("local", async () => (await import("playwright-core")).chromium.launch({ headless, args })),
];
process.exit(results[0] ? 0 : 1);
