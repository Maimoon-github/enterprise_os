import { describe, expect, test } from "bun:test";
import { audioFormatFor, buildTranscriptionPrompt, parseTranscriptResponse } from "./transcription";

describe("audioFormatFor", () => {
  test("audio/ogg and codec variants map to ogg", () => {
    expect(audioFormatFor("audio/ogg")).toBe("ogg");
    expect(audioFormatFor("audio/ogg; codecs=opus")).toBe("ogg");
  });

  test("audio/webm and anything else falls back to webm", () => {
    expect(audioFormatFor("audio/webm")).toBe("webm");
    expect(audioFormatFor("audio/webm; codecs=opus")).toBe("webm");
    expect(audioFormatFor("audio/mp4")).toBe("webm");
    expect(audioFormatFor(null)).toBe("webm");
    expect(audioFormatFor(undefined)).toBe("webm");
  });
});

describe("buildTranscriptionPrompt", () => {
  test("includes the lead's name and company when known", () => {
    const prompt = buildTranscriptionPrompt({ leadName: "Priya Sharma", companyName: "Acme Corp" });
    expect(prompt).toContain("Priya Sharma, Acme Corp");
    expect(prompt).toContain("rep");
    expect(prompt).toContain("lead");
  });

  test("still reads sensibly with nothing known about the lead", () => {
    const prompt = buildTranscriptionPrompt({ leadName: null, companyName: null });
    expect(prompt).not.toContain("()");
    expect(prompt).toContain("a sales rep to a lead. ");
    expect(prompt.length).toBeGreaterThan(0);
  });
});

describe("parseTranscriptResponse", () => {
  test("parses a well-formed response", () => {
    const parsed = parseTranscriptResponse({
      language: "hi-en",
      summary: "Rep pitched the product; lead asked for a follow-up call Tuesday.",
      utterances: [
        { startSeconds: 5, speaker: "rep", text: "Hi, this is Sam calling." },
        { startSeconds: 2, speaker: "lead", text: "Hello?" },
      ],
    });
    expect(parsed).toEqual({
      language: "hi-en",
      summary: "Rep pitched the product; lead asked for a follow-up call Tuesday.",
      // Sorted by startSeconds.
      utterances: [
        { startSeconds: 2, speaker: "lead", text: "Hello?" },
        { startSeconds: 5, speaker: "rep", text: "Hi, this is Sam calling." },
      ],
    });
  });

  test("merges consecutive fragments from the same speaker", () => {
    const parsed = parseTranscriptResponse({
      language: "en",
      summary: "s",
      utterances: [
        { startSeconds: 0, speaker: "rep", text: "Hi there," },
        { startSeconds: 1, speaker: "rep", text: "how are you?" },
        { startSeconds: 3, speaker: "lead", text: "Good, thanks." },
      ],
    });
    expect(parsed?.utterances).toEqual([
      { startSeconds: 0, speaker: "rep", text: "Hi there, how are you?" },
      { startSeconds: 3, speaker: "lead", text: "Good, thanks." },
    ]);
  });

  test("drops malformed utterances but keeps the valid ones", () => {
    const parsed = parseTranscriptResponse({
      language: "en",
      summary: "s",
      utterances: [
        { startSeconds: 0, speaker: "rep", text: "valid" },
        { startSeconds: 1, speaker: "narrator", text: "bad speaker" },
        { startSeconds: 2, speaker: "lead", text: "" },
        { startSeconds: "3", speaker: "lead", text: "bad startSeconds type" },
        "not even an object",
        { startSeconds: 4, speaker: "lead", text: "also valid" },
      ],
    });
    expect(parsed?.utterances).toEqual([
      { startSeconds: 0, speaker: "rep", text: "valid" },
      { startSeconds: 4, speaker: "lead", text: "also valid" },
    ]);
  });

  test("clamps a negative startSeconds to 0", () => {
    const parsed = parseTranscriptResponse({
      language: "en",
      summary: "s",
      utterances: [{ startSeconds: -5, speaker: "rep", text: "hi" }],
    });
    expect(parsed?.utterances[0].startSeconds).toBe(0);
  });

  test("falls back to a placeholder summary when the model omits one", () => {
    const parsed = parseTranscriptResponse({
      language: null,
      summary: "",
      utterances: [{ startSeconds: 0, speaker: "rep", text: "hi" }],
    });
    expect(parsed?.summary).toBe("No summary was returned.");
    expect(parsed?.language).toBeNull();
  });

  test("returns null when nothing valid survives", () => {
    expect(parseTranscriptResponse({ language: "en", summary: "s", utterances: [] })).toBeNull();
    expect(parseTranscriptResponse({ language: "en", summary: "s", utterances: [{ speaker: "narrator", text: "x", startSeconds: 0 }] })).toBeNull();
    expect(parseTranscriptResponse(null)).toBeNull();
    expect(parseTranscriptResponse("nope")).toBeNull();
    expect(parseTranscriptResponse({})).toBeNull();
  });
});

describe("buildTranscriptionPrompt — ringing before the pick-up", () => {
  test("says how much ringing to skip when the recording starts before the pick-up", () => {
    const prompt = buildTranscriptionPrompt({ leadName: null, companyName: null, recordingOffsetMs: 7400 });
    expect(prompt).toContain("about 7 seconds before the lead picks up");
  });
  test("says nothing about ringing without an offset", () => {
    expect(buildTranscriptionPrompt({ leadName: null, companyName: null })).not.toContain("picks up");
  });

  test("an incoming call: the lead is the caller", () => {
    const prompt = buildTranscriptionPrompt({ leadName: "Priya Sharma", companyName: null, inbound: true });
    expect(prompt).toContain("placed by a lead (Priya Sharma) to a sales rep's number");
    expect(prompt).not.toContain("The rep is the caller");
    expect(buildTranscriptionPrompt({ leadName: null, companyName: null, recordingOffsetMs: 300 })).not.toContain("picks up");
  });
});
