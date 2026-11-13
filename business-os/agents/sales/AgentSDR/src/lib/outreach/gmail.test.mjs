import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildRawEmailMessage } from "./gmail.ts";

describe("Gmail raw-message recipients", () => {
  it("retains CC and BCC headers for Gmail API delivery", async () => {
    const raw = await buildRawEmailMessage({
      from: "sender@example.com",
      to: ["to@example.com"],
      cc: ["cc@example.com"],
      bcc: ["bcc@example.com"],
      subject: "Recipient test",
      text: "Body",
    });
    const headers = raw.toString().split(/\r?\n\r?\n/, 1)[0];

    assert.match(headers, /^To: to@example\.com$/mi);
    assert.match(headers, /^Cc: cc@example\.com$/mi);
    assert.match(headers, /^Bcc: bcc@example\.com$/mi);
  });

  it("does not create CC or BCC headers when no recipients were supplied", async () => {
    const raw = await buildRawEmailMessage({
      from: "sender@example.com",
      to: ["to@example.com"],
      subject: "Recipient test",
      text: "Body",
    });
    const headers = raw.toString().split(/\r?\n\r?\n/, 1)[0];

    assert.doesNotMatch(headers, /^Cc:/mi);
    assert.doesNotMatch(headers, /^Bcc:/mi);
  });
});
