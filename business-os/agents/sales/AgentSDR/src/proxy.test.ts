import { describe, expect, test } from "bun:test";
import * as pageStaticInfo from "next/dist/build/analysis/get-page-static-info";
import { getMiddlewareRouteMatcher } from "next/dist/shared/lib/router/utils/middleware-route-matcher";
import { config } from "./proxy";

// Exported by the module, though not by its type declarations.
const { getMiddlewareMatchers } = pageStaticInfo as unknown as {
  getMiddlewareMatchers: (matcher: unknown, nextConfig: unknown) => Parameters<typeof getMiddlewareRouteMatcher>[0];
};

/**
 * The matcher compiled the way Next.js compiles it. What it leaves out never
 * reaches the proxy — which matters for a call relay's upload stream:
 * Next.js holds back the body of a request the proxy sees until it ends.
 */
const matches = getMiddlewareRouteMatcher(getMiddlewareMatchers(config.matcher, {}));
const runsProxy = (pathname: string, headers: Record<string, string> = {}) => matches(pathname, { headers } as never, {});

const CALL = "0b6a3c1e-5a43-4c6e-9d2a-2a2f3a3b4c5d";
const STREAM = { "x-relay-stream": "1" };

describe("proxy matcher", () => {
  test("a relay upload stream skips the proxy, on both sides' relay paths", () => {
    expect(runsProxy(`/api/calls/${CALL}/relay`, STREAM)).toBe(false);
    expect(runsProxy(`/api/call-recorder/calls/${CALL}/relay`, STREAM)).toBe(false);
  });

  test("every other request to the relay paths still goes through it", () => {
    expect(runsProxy(`/api/calls/${CALL}/relay`)).toBe(true);
    expect(runsProxy(`/api/call-recorder/calls/${CALL}/relay`)).toBe(true);
    expect(runsProxy(`/api/calls/${CALL}/relay/hangup`, STREAM)).toBe(true);
  });

  test("the stream header skips nothing anywhere else", () => {
    for (const pathname of ["/", "/settings", `/api/calls/${CALL}`, "/api/crm/conversations", `/api/calls/${CALL}/relay/`]) {
      expect(runsProxy(pathname, STREAM)).toBe(true);
    }
  });

  test("static files still skip it", () => {
    expect(runsProxy("/logo.png")).toBe(false);
    expect(runsProxy("/_next/static/chunks/app.js")).toBe(false);
  });
});
