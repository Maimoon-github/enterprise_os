import { expect, test } from "bun:test";
import { pcm16Wav } from "./wav";

test("pcm16Wav writes a 16 kHz mono WAV header and the samples little-endian", () => {
  const wav = pcm16Wav(Int16Array.from([0, 1000, -1000, 32767]), 16_000);
  const view = new DataView(wav.buffer);
  expect(new TextDecoder().decode(wav.subarray(0, 4))).toBe("RIFF");
  expect(new TextDecoder().decode(wav.subarray(8, 16))).toBe("WAVEfmt ");
  expect(view.getUint16(22, true)).toBe(1);
  expect(view.getUint32(24, true)).toBe(16_000);
  expect(view.getUint32(40, true)).toBe(8);
  expect(view.getInt16(46, true)).toBe(1000);
  expect(view.getInt16(48, true)).toBe(-1000);
  expect(wav.length).toBe(52);
});
