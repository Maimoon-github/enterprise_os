import { describe, expect, test } from "bun:test";
import { gridRowToPersonInput, templateVariableKey } from "./gridCampaigns.ts";

describe("grid campaign mapping", () => {
  test("writes mapped values to canonical fields and preserves only unmapped values in raw", () => {
    const result = gridRowToPersonInput(
      { c1: "Pat", c2: "pat@example.com", c3: "APAC", c4: 42 },
      [
        { key: "c1", name: "First Name" },
        { key: "c2", name: "Email" },
        { key: "c3", name: "Sales Region" },
        { key: "c4", name: "Intent score (%)" },
      ],
      { firstName: "c1", email: "c2" },
    );
    expect(result.firstName).toBe("Pat");
    expect(result.email).toBe("pat@example.com");
    expect(result.raw).toEqual({
      "Sales Region": "APAC",
      salesRegion: "APAC",
      "Intent score (%)": 42,
      intentScore: 42,
    });
  });

  test("creates tokens accepted by the template renderer", () => {
    expect(templateVariableKey("First Name")).toBe("firstName");
    expect(templateVariableKey("2026 Priority!")).toBe("field2026Priority");
  });
});
