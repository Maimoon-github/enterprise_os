import { describe, expect, test } from "bun:test";
import { csvCell, serializeCsv, UTF8_BOM } from "./csv.ts";

describe("grid CSV serialization", () => {
  test("writes nullish values as blanks and primitives as text", () => {
    expect(serializeCsv([[null, undefined, 42, -7.5, true, false]])).toBe(",,42,-7.5,true,false");
  });

  test("quotes commas, quotes, and either newline style", () => {
    expect(csvCell('Ada, "Countess"')).toBe('"Ada, ""Countess"""');
    expect(serializeCsv([["line 1\nline 2"], ["left\rright"]])).toBe(
      '"line 1\nline 2"\r\n"left\rright"',
    );
  });

  test("JSON-serializes arrays and objects without losing their shape", () => {
    expect(serializeCsv([[["sales", "ops"], { score: 9, active: true }]])).toBe(
      '"[""sales"",""ops""]","{""score"":9,""active"":true}"',
    );
  });

  test("neutralizes formula-like strings but leaves numeric negatives intact", () => {
    expect(serializeCsv([["=1+1", " +cmd", "-2+3", "@SUM(A1)", "\tcmd", -23]])).toBe(
      "'=1+1,' +cmd,'-2+3,'@SUM(A1),'\tcmd,-23",
    );
  });

  test("exposes the UTF-8 BOM separately from the pure CSV body", () => {
    expect(UTF8_BOM).toBe("\uFEFF");
    expect(serializeCsv([["Name"], ["Renée"]])).toBe("Name\r\nRenée");
  });
});
