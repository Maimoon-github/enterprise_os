import { test, expect } from "bun:test";
import {
  assertPublicUrl,
  interpolateJsonBody,
  interpolateUrl,
  isAllowedHttpSecretEnvVar,
  isBlockedAddress,
  isIdempotentMethod,
  stripLineBreaks,
} from "./runners/http";

test("blocks loopback, private, link-local, CGNAT and unspecified IPv4", () => {
  for (const ip of [
    "127.0.0.1", "127.255.255.255", "10.0.0.1", "172.16.0.1", "172.31.255.255", "192.168.1.1",
    "169.254.169.254", "100.64.0.1", "100.127.255.255", "0.0.0.0", "224.0.0.1", "255.255.255.255",
  ]) expect(isBlockedAddress(ip)).toBe(true);
});

test("allows ordinary public IPv4, including the edges of private ranges", () => {
  for (const ip of ["8.8.8.8", "1.1.1.1", "172.15.255.255", "172.32.0.1", "100.63.255.255", "100.128.0.1", "93.184.216.34"]) {
    expect(isBlockedAddress(ip)).toBe(false);
  }
});

test("blocks IPv6 loopback, unspecified, unique-local, link-local and multicast", () => {
  for (const ip of ["::1", "::", "fc00::1", "fd12:3456::1", "fe80::1", "fe80::1%eth0", "ff02::1", "0:0:0:0:0:0:0:1"]) {
    expect(isBlockedAddress(ip)).toBe(true);
  }
  expect(isBlockedAddress("2606:4700:4700::1111")).toBe(false);
});

test("blocks IPv6 forms that embed a private IPv4", () => {
  for (const ip of [
    "::ffff:127.0.0.1", "::ffff:7f00:1", "::ffff:10.0.0.1", "::ffff:169.254.169.254", "::ffff:a9fe:a9fe",
    "64:ff9b::7f00:1", "2002:7f00:1::1", "::127.0.0.1",
  ]) expect(isBlockedAddress(ip)).toBe(true);
  expect(isBlockedAddress("::ffff:8.8.8.8")).toBe(false);
});

test("anything that is not an IP address is blocked", () => {
  expect(isBlockedAddress("not-an-ip")).toBe(true);
  expect(isBlockedAddress("")).toBe(true);
});

test("WHATWG URL folds decimal, hex, octal and short IPv4 spellings before the check", () => {
  for (const host of ["2130706433", "0x7f.1", "0177.0.0.1", "127.1", "0x7f000001"]) {
    const hostname = new URL(`http://${host}/`).hostname;
    expect(hostname).toBe("127.0.0.1");
    expect(isBlockedAddress(hostname)).toBe(true);
  }
  expect(new URL("http://[::ffff:127.0.0.1]/").hostname).toBe("[::ffff:7f00:1]");
});

test("assertPublicUrl checks every resolved address", async () => {
  const resolve = (map: Record<string, string[]>) => async (host: string) => {
    if (!map[host]) throw new Error("ENOTFOUND");
    return map[host];
  };
  const dns = resolve({
    "public.example": ["93.184.216.34"],
    "mixed.example": ["93.184.216.34", "10.0.0.5"],
    "internal.example": ["127.0.0.1"],
  });
  await expect(assertPublicUrl(new URL("https://public.example/x"), dns, false)).resolves.toBeUndefined();
  await expect(assertPublicUrl(new URL("https://mixed.example/x"), dns, false)).rejects.toThrow(/private or internal/);
  await expect(assertPublicUrl(new URL("https://internal.example/x"), dns, false)).rejects.toThrow(/private or internal/);
  await expect(assertPublicUrl(new URL("http://169.254.169.254/latest/meta-data"), dns, false)).rejects.toThrow();
  await expect(assertPublicUrl(new URL("http://[::1]:3001/"), dns, false)).rejects.toThrow();
  await expect(assertPublicUrl(new URL("http://missing.example/"), dns, false)).rejects.toThrow(/resolve/);
});

test("the escape hatch skips the check", async () => {
  await expect(assertPublicUrl(new URL("http://127.0.0.1:3001/"), async () => ["127.0.0.1"], true)).resolves.toBeUndefined();
});

test("credential env vars must carry the GRID_HTTP_SECRET_ prefix", () => {
  expect(isAllowedHttpSecretEnvVar("GRID_HTTP_SECRET_APOLLO")).toBe(true);
  expect(isAllowedHttpSecretEnvVar("GRID_HTTP_SECRET_")).toBe(false);
  expect(isAllowedHttpSecretEnvVar("DATABASE_URL")).toBe(false);
  expect(isAllowedHttpSecretEnvVar("INTEGRATION_CREDENTIALS_KEY")).toBe(false);
  expect(isAllowedHttpSecretEnvVar("grid_http_secret_x")).toBe(false);
  expect(isAllowedHttpSecretEnvVar("GRID_HTTP_SECRET_A B")).toBe(false);
});

test("URL values are percent-encoded; a leading token (the origin) stays raw", () => {
  expect(interpolateUrl("https://api.test/search?q={{q}}", { q: "a&admin=1 #x" })).toBe(
    "https://api.test/search?q=a%26admin%3D1%20%23x",
  );
  expect(interpolateUrl("https://api.test/u/{{id}}", { id: "../etc" })).toBe("https://api.test/u/..%2Fetc");
  expect(interpolateUrl("{{site}}/x", { site: "https://example.com" })).toBe("https://example.com/x");
  expect(interpolateUrl("https://api.test/?a={{missing}}", {})).toBe("https://api.test/?a=");
});

test("JSON body values are escaped inside strings and quoted when bare", () => {
  const body = interpolateJsonBody('{"name":"{{name}}","n":{{n}},"who":{{who}}}', {
    name: 'Bob "the" \\ builder\n',
    n: 3,
    who: "x",
  });
  expect(JSON.parse(body)).toEqual({ name: 'Bob "the" \\ builder\n', n: 3, who: "x" });
  // A quote cannot close the string and add keys.
  const injected = interpolateJsonBody('{"a":"{{v}}"}', { v: '","admin":true,"x":"' });
  expect(JSON.parse(injected)).toEqual({ a: '","admin":true,"x":"' });
  expect(JSON.parse(interpolateJsonBody('{"a":{{v}}}', {}))).toEqual({ a: null });
  expect(JSON.parse(interpolateJsonBody('{"a":{{v}}}', { v: { k: 1 } }))).toEqual({ a: { k: 1 } });
  expect(JSON.parse(interpolateJsonBody('{"a":"x {{v}}"}', { v: { k: 1 } }))).toEqual({ a: 'x {"k":1}' });
});

test("header values lose CR/LF; only GET/HEAD are idempotent", () => {
  expect(stripLineBreaks("abc\r\nX-Evil: 1")).toBe("abc X-Evil: 1");
  expect(isIdempotentMethod("GET")).toBe(true);
  expect(isIdempotentMethod("HEAD")).toBe(true);
  for (const m of ["POST", "PUT", "PATCH", "DELETE"]) expect(isIdempotentMethod(m)).toBe(false);
});

test("a bare token holding JSON-looking text is inserted as that value", () => {
  const body = interpolateJsonBody('{"n":{{n}},"ok":{{ok}},"ids":{{ids}}}', { n: "42", ok: "true", ids: "[1,2]" });
  expect(JSON.parse(body)).toEqual({ n: 42, ok: true, ids: [1, 2] });
});
