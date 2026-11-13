import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { buildClassificationContext } from "./context";
import type { ClassificationContextInput } from "./ai/types";

function fixture(): ClassificationContextInput {
  return {
    categories: [
      { key: "customer", label: "Customer" },
      { key: "interested", label: "Interested" },
      { key: "not_interested", label: "Not Interested" },
      { key: "other", label: "Other" },
    ],
    subcategories: [{
      id: "subcategory-demo",
      categoryKey: "interested",
      key: "demo_requested",
      name: "Demo requested",
      classificationGuidance: "Use when the person explicitly asks to see the product.",
      reviewRequired: false,
    }],
    person: {
      id: "person-1",
      fullName: "Priya Rao",
      email: "priya@example.com",
      title: "VP Sales",
      attributes: { region: "APAC" },
    },
    company: {
      id: "company-1",
      name: "Example",
      domain: "example.com",
      description: "A software company",
    },
    currentClassification: {
      categoryKey: null,
      subcategoryKey: null,
      categorySource: null,
      categoryLocked: false,
    },
    campaignSummary: {
      channel: "email",
      campaignId: "campaign-1",
      name: "August outbound",
      source: "native-email",
      summary: "Targeted sales leaders in APAC.",
    },
    latestInboundMessage: {
      id: "message-3",
      channel: "email",
      direction: "inbound",
      sentAt: "2026-08-31T12:00:00.000Z",
      subject: "Re: product",
      bodyText: "Can you show me a demo next Tuesday?",
    },
    recentConversation: [
      {
        id: "message-1",
        channel: "email",
        direction: "outbound",
        sentAt: "2026-08-29T12:00:00.000Z",
        bodyText: "Initial outreach",
      },
      {
        id: "message-2",
        channel: "email",
        direction: "outbound",
        sentAt: "2026-08-30T12:00:00.000Z",
        bodyText: "Follow-up",
      },
      {
        id: "message-3",
        channel: "email",
        direction: "inbound",
        sentAt: "2026-08-31T12:00:00.000Z",
        bodyText: "Can you show me a demo next Tuesday?",
      },
    ],
  };
}

describe("CRM classification context", () => {
  test("contains taxonomy, profiles, campaign, latest inbound, and a chronological thread", () => {
    const context = buildClassificationContext(fixture());

    assert.equal(context.snapshot.person.fullName, "Priya Rao");
    assert.equal(context.snapshot.company?.domain, "example.com");
    assert.equal(context.snapshot.campaignSummary?.name, "August outbound");
    assert.equal(context.snapshot.taxonomy.subcategories[0]?.key, "demo_requested");
    assert.equal(context.snapshot.latestInboundMessage.id, "message-3");
    assert.deepEqual(context.snapshot.recentConversation.map((message) => message.id), [
      "message-1",
      "message-2",
    ]);
    assert.match(context.prompt, /Can you show me a demo next Tuesday\?/);
  });

  test("carries email participants into the snapshot only when present", () => {
    const input = fixture();
    input.recentConversation[0]!.participants = { from: "me@us.com", to: ["priya@example.com"], cc: ["boss@example.com"] };
    const context = buildClassificationContext(input);
    const [first, second] = context.snapshot.recentConversation;
    assert.deepEqual(first?.participants?.cc, ["boss@example.com"]);
    assert.equal("participants" in (second ?? {}), false);
  });

  test("keeps the prompt inside the requested budget and drops whole older messages", () => {
    const input = fixture();
    input.latestInboundMessage.bodyText = "latest ".repeat(1_000);
    input.recentConversation = Array.from({ length: 6 }, (_, index) => ({
      id: `old-${index}`,
      channel: "email" as const,
      direction: index % 2 ? "inbound" as const : "outbound" as const,
      sentAt: new Date(Date.UTC(2026, 7, 20 + index)).toISOString(),
      bodyText: `complete-message-${index} ${"content ".repeat(300)}`,
    }));

    const context = buildClassificationContext(input, { maxTokens: 512 });

    assert.ok(context.prompt.length <= 512 * 4);
    assert.ok(context.estimatedTokens <= 512);
    assert.equal(context.truncated, true);
    assert.ok(context.omittedMessageCount > 0);
    for (const message of context.snapshot.recentConversation) {
      assert.equal(message.bodyText, input.recentConversation.find((item) => item.id === message.id)?.bodyText);
    }
  });

  test("rejects outbound latest messages and invalid timestamps", () => {
    const outbound = fixture();
    outbound.latestInboundMessage.direction = "outbound";
    assert.throws(() => buildClassificationContext(outbound), /must be inbound/);

    const invalidDate = fixture();
    invalidDate.latestInboundMessage.sentAt = "not-a-date";
    assert.throws(() => buildClassificationContext(invalidDate), /invalid sentAt/);
  });

  test("includes always-included Knowledge documents in the snapshot and prompt", () => {
    const input = fixture();
    input.knowledge = [
      {
        documentId: "doc-1",
        title: "  Sender & Contact Details  ",
        kind: "company",
        content: "Product: Widget Pro. Sender: sales@example.com. Cal.com: https://cal.com/example/demo.",
      },
      // A duplicate documentId must be deduped, and an empty-content document dropped.
      {
        documentId: "doc-1",
        title: "Sender & Contact Details (duplicate)",
        kind: "company",
        content: "Should not appear.",
      },
      { documentId: "doc-2", title: "Empty", kind: "custom", content: "   " },
    ];

    const context = buildClassificationContext(input);

    assert.deepEqual(context.snapshot.knowledge, [{
      documentId: "doc-1",
      title: "Sender & Contact Details",
      kind: "company",
      content: "Product: Widget Pro. Sender: sales@example.com. Cal.com: https://cal.com/example/demo.",
    }]);
    assert.match(context.prompt, /Widget Pro/);
    assert.match(context.prompt, /cal\.com\/example\/demo/);
  });

  test("drops Knowledge before the company description under a tight token budget", () => {
    const input = fixture();
    input.knowledge = [{
      documentId: "doc-1",
      title: "Sender & Contact Details",
      kind: "company",
      content: "knowledge-content ".repeat(80),
    }];

    const context = buildClassificationContext(input, { maxTokens: 620 });

    assert.equal(context.snapshot.knowledge.length, 0);
    assert.equal(context.snapshot.company?.description, "A software company");
    assert.equal(context.truncated, true);
  });

  test("still builds a valid context when knowledge is omitted", () => {
    const input = fixture();
    delete input.knowledge;

    const context = buildClassificationContext(input);

    assert.deepEqual(context.snapshot.knowledge, []);
  });
});
