import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, test } from "node:test";
import { hostedAuthCallbackUrls } from "./hostedAuthUrls";

const original = {
  appUrl: process.env.NEXT_PUBLIC_APP_URL,
  authUrl: process.env.BETTER_AUTH_URL,
};

function restore(name: string, value: string | undefined) {
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
}

// These cases drive the legacy NEXT_PUBLIC_APP_URL; BETTER_AUTH_URL (which
// takes precedence) is cleared so a developer's own env cannot leak in.
beforeEach(() => {
  delete process.env.BETTER_AUTH_URL;
});

afterEach(() => {
  restore("NEXT_PUBLIC_APP_URL", original.appUrl);
  restore("BETTER_AUTH_URL", original.authUrl);
});

describe("hostedAuthCallbackUrls", () => {
  test("returns the user to the public origin by default", () => {
    process.env.NEXT_PUBLIC_APP_URL = "https://agentsdr.ai/";

    const urls = hostedAuthCallbackUrls(null, "s3cret");

    assert.equal(urls.successRedirectUrl, "https://agentsdr.ai/settings/linkedin-accounts?unipile=success");
    assert.equal(urls.failureRedirectUrl, "https://agentsdr.ai/settings/linkedin-accounts?unipile=failure");
    assert.equal(
      urls.notifyUrl,
      "https://agentsdr.ai/api/webhooks/unipile-account?secret=s3cret"
    );
  });

  test("adds the organization to notify_url when given", () => {
    process.env.NEXT_PUBLIC_APP_URL = "https://agentsdr.ai";

    const urls = hostedAuthCallbackUrls(null, "s3cret", "org-1");

    assert.equal(
      urls.notifyUrl,
      "https://agentsdr.ai/api/webhooks/unipile-account?secret=s3cret&org=org-1"
    );
  });

  test("returns a dev session to localhost rather than production", () => {
    process.env.NEXT_PUBLIC_APP_URL = "https://agentsdr.ai";

    const urls = hostedAuthCallbackUrls("http://localhost:3000", "s3cret");

    assert.equal(urls.successRedirectUrl, "http://localhost:3000/settings/linkedin-accounts?unipile=success");
    // notify_url still points at the public origin: Unipile calls it from their
    // servers and cannot reach a developer's machine.
    assert.match(urls.notifyUrl ?? "", /^https:\/\/agentsdr\.ai\//);
  });

  test("ignores a non-local Origin header, so it cannot become an open redirect", () => {
    process.env.NEXT_PUBLIC_APP_URL = "https://agentsdr.ai";

    const urls = hostedAuthCallbackUrls("https://evil.example.com");

    assert.equal(urls.successRedirectUrl, "https://agentsdr.ai/settings/linkedin-accounts?unipile=success");
    assert.equal(urls.failureRedirectUrl, "https://agentsdr.ai/settings/linkedin-accounts?unipile=failure");
  });

  test("omits notify_url when it would point at localhost", () => {
    process.env.NEXT_PUBLIC_APP_URL = "http://localhost:3000";

    assert.equal(hostedAuthCallbackUrls("http://localhost:3000", "s3cret").notifyUrl, undefined);
  });

  test("omits notify_url when the stored secret is empty", () => {
    process.env.NEXT_PUBLIC_APP_URL = "https://agentsdr.ai";

    assert.equal(hostedAuthCallbackUrls(null, "").notifyUrl, undefined);
  });

  test("throws when there is no origin to return to", () => {
    delete process.env.NEXT_PUBLIC_APP_URL;

    assert.throws(() => hostedAuthCallbackUrls(null), /BETTER_AUTH_URL/);
  });
  test("prefers the runtime BETTER_AUTH_URL over the build-time NEXT_PUBLIC_APP_URL", () => {
    process.env.NEXT_PUBLIC_APP_URL = "https://build-time.example.com";
    process.env.BETTER_AUTH_URL = "https://runtime.example.com/";

    const urls = hostedAuthCallbackUrls(null, "s3cret");

    assert.equal(urls.successRedirectUrl, "https://runtime.example.com/settings/linkedin-accounts?unipile=success");
  });
});
