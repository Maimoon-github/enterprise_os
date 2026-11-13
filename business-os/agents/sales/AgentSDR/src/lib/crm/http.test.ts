import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  assertSameOriginMutation,
  CrmRequestError,
  requireIdempotencyKey,
} from "./http";

describe("CRM mutation request security", () => {
  test("requires an exact same-origin mutation for direct requests", () => {
    const headers = new Headers({ origin: "https://crm.example", "sec-fetch-site": "same-origin" });
    assert.doesNotThrow(() =>
      assertSameOriginMutation({ url: "https://crm.example/api/crm/test", method: "POST", headers }),
    );
    headers.set("origin", "https://attacker.example");
    assert.throws(
      () => assertSameOriginMutation({ url: "https://crm.example/api/crm/test", method: "POST", headers }),
      (error: unknown) => error instanceof CrmRequestError && error.status === 403,
    );
  });

  test("accepts a legitimate browser mutation after a reverse proxy rewrites the URL", () => {
    const headers = new Headers({
      origin: "https://crm.example",
      "sec-fetch-site": "same-origin",
    });
    assert.doesNotThrow(() => assertSameOriginMutation({
      url: "http://127.0.0.1:3000/api/crm/test",
      method: "PATCH",
      headers,
    }));
  });

  test("uses unambiguous forwarded host and protocol for clients without Fetch Metadata", () => {
    const headers = new Headers({
      origin: "https://crm.example",
      host: "127.0.0.1:3000",
      "x-forwarded-host": "crm.example",
      "x-forwarded-proto": "https",
    });
    assert.doesNotThrow(() => assertSameOriginMutation({
      url: "http://127.0.0.1:3000/api/crm/test",
      method: "POST",
      headers,
    }));
  });

  test("rejects missing, malformed, same-site, and cross-site origins", () => {
    const request = { url: "https://crm.example/api/crm/test", method: "POST" };
    for (const headers of [
      new Headers({ "sec-fetch-site": "same-origin" }),
      new Headers({ origin: "null", "sec-fetch-site": "same-origin" }),
      new Headers({ origin: "https://crm.example", "sec-fetch-site": "same-site" }),
      new Headers({ origin: "https://attacker.example", "sec-fetch-site": "cross-site" }),
    ]) {
      assert.throws(
        () => assertSameOriginMutation({ ...request, headers }),
        (error: unknown) => error instanceof CrmRequestError && error.status === 403,
      );
    }
  });

  test("validates durable idempotency keys", () => {
    assert.equal(
      requireIdempotencyKey(new Headers({ "idempotency-key": "send:01991e73-abcdef" })),
      "send:01991e73-abcdef",
    );
    assert.throws(() => requireIdempotencyKey(new Headers()), /Idempotency-Key/);
  });
});
