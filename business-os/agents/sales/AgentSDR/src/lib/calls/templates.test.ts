import { describe, expect, test } from "bun:test";
import { CONTACT_CALL_STATUSES, CONTACT_CALL_STATUS_DEFINITIONS } from "./contract";
import { followUpMessageFor, greetingName, renderTemplate } from "./templates";

describe("greetingName", () => {
  test("prefers the first name", () => {
    expect(greetingName({ firstName: "Rahul", fullName: "Rahul Mehta" })).toBe("Rahul");
  });
  test("falls back to the first word of the full name", () => {
    expect(greetingName({ firstName: null, fullName: "  Neha Sharma " })).toBe("Neha");
  });
  test("says 'there' when there is no name at all", () => {
    expect(greetingName({ firstName: " ", fullName: null })).toBe("there");
  });
});

describe("renderTemplate", () => {
  test("fills every {{firstName}}, tolerating spacing and case", () => {
    expect(renderTemplate("Hi {{firstName}} / {{ FirstName }}", { firstName: "Asha", fullName: null })).toBe(
      "Hi Asha / Asha",
    );
  });
});

describe("followUpMessageFor", () => {
  const lead = { firstName: "Asha", fullName: null };
  test("offers no message for statuses without a template", () => {
    expect(followUpMessageFor("wrong_number", lead)).toBeNull();
    expect(followUpMessageFor("new", lead)).toBeNull();
  });
  test("greets the lead by first name after an unanswered call", () => {
    expect(followUpMessageFor("no_answer", lead)).toStartWith("Hi Asha,");
  });
  test("every template-bearing status renders without leftover placeholders", () => {
    for (const status of CONTACT_CALL_STATUSES) {
      const message = followUpMessageFor(status, lead);
      if (CONTACT_CALL_STATUS_DEFINITIONS[status].template === null) {
        expect(message).toBeNull();
        continue;
      }
      expect(message).not.toContain("{{");
    }
  });
});
