import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { classifyLinkedinIdentifier } from "../../../scripts/audit-legacy-linkedin-identifiers.ts";

describe("classifyLinkedinIdentifier", () => {
  it("classifies supported LinkedIn identifier forms", () => {
    assert.equal(classifyLinkedinIdentifier("https://linkedin.com/in/example"), "public_url");
    assert.equal(classifyLinkedinIdentifier("https://www.linkedin.com/sales/lead/abc"), "sales_navigator");
    assert.equal(classifyLinkedinIdentifier("https://www.linkedin.com/talent/profile/abc"), "recruiter");
    assert.equal(classifyLinkedinIdentifier("ACoAAB123_xyz"), "provider_id");
    assert.equal(classifyLinkedinIdentifier("urn%3Ali%3Afsd_profile%3Aabc"), "encoded");
    assert.equal(classifyLinkedinIdentifier("public-slug"), "public_slug");
    assert.equal(classifyLinkedinIdentifier("not a valid id"), "opaque");
  });
});
