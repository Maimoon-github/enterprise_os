import type { BrowserContext, Locator, Page } from "playwright-core";

const WA_URL = "https://web.whatsapp.com/";

export type WhatsAppState = "ready" | "logged_out" | "timeout";

export async function openWhatsApp(context: BrowserContext): Promise<Page> {
  const existing = context.pages().find((p) => p.url().startsWith(WA_URL));
  const page = existing ?? context.pages().find((p) => p.url() === "about:blank" || p.url() === "chrome://newtab/") ?? (await context.newPage());
  await page.goto(WA_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
  return page;
}

/**
 * The language WhatsApp Web came up in ("en", "hi", …). It follows the
 * browser profile's language, and the extension finds "Voice call" and "End
 * call" by their English labels, as the link flow does "Log in with phone
 * number" — so a profile must be set to English. A GoLogin profile set its
 * language from the IP and WhatsApp came up in Hindi (12 Oct 2026); the
 * worker reports that rather than override the profile's fingerprint.
 */
export async function whatsAppLanguage(page: Page): Promise<string> {
  return page.evaluate(() => document.documentElement.lang || navigator.language || "").catch(() => "");
}

export function isEnglish(language: string): boolean {
  return language === "" || /^en\b/i.test(language);
}

/**
 * The account WhatsApp Web is logged in as, E.164 ("+919876543210"), or null.
 * WhatsApp keeps it in localStorage as `last-wid-md` ("919876543210:1@c.us",
 * the ":1" being this linked device), `last-wid` on older builds.
 */
export async function loggedInPhone(page: Page): Promise<string | null> {
  const wid = await page
    .evaluate(() => localStorage.getItem("last-wid-md") ?? localStorage.getItem("last-wid"))
    .catch(() => null);
  const digits = wid ? /(\d{7,15})[:@]/.exec(wid)?.[1] : null;
  return digits ? `+${digits}` : null;
}

/** The chat list's pane — present in every language, unlike its aria-label. */
const READY_SELECTOR = '#pane-side, #side div[role="grid"], [aria-label="Chat list"]';
/** The login QR — a canvas with an aria-label in whatever language WhatsApp is in. */
const LOGIN_SELECTOR = "canvas[aria-label]";
const LOGIN_TEXT = /log in with phone number|link with phone number|steps to log in|scan the qr code/i;

async function isVisible(page: Page, selector: string): Promise<boolean> {
  return page.locator(selector).first().isVisible().catch(() => false);
}

export async function waitForWhatsAppState(page: Page, timeoutMs: number): Promise<WhatsAppState> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await isVisible(page, READY_SELECTOR)) return "ready";
    if (await isVisible(page, LOGIN_SELECTOR)) return "logged_out";
    const text = await page.evaluate(() => document.body?.innerText ?? "").catch(() => "");
    if (LOGIN_TEXT.test(text)) return "logged_out";
    await page.waitForTimeout(1000).catch(() => {});
  }
  return "timeout";
}

/** The login screen is up: its QR, or the phone-number form. Gone once the phone has linked. */
export async function isLoginScreen(page: Page): Promise<boolean> {
  return (
    (await isVisible(page, LOGIN_SELECTOR)) ||
    (await isVisible(page, 'input[aria-label*="phone number" i]')) ||
    LOGIN_TEXT.test(await page.evaluate(() => document.body?.innerText ?? "").catch(() => ""))
  );
}

/** Waits up to `timeoutMs` for the chat list — WhatsApp Web logged in and loaded. */
export async function waitForReady(page: Page, timeoutMs: number): Promise<boolean> {
  return page
    .locator(READY_SELECTOR)
    .first()
    .waitFor({ state: "visible", timeout: timeoutMs })
    .then(() => true)
    .catch(() => false);
}

const CODE_RE = /\b[A-Z0-9]{4}-?[A-Z0-9]{4}\b/;

async function readLinkCode(page: Page): Promise<string | null> {
  try {
    const attr = await page.locator("[data-link-code]").first().getAttribute("data-link-code", { timeout: 1500 });
    if (attr) {
      const code = attr.split(",").map((c) => c.trim()).join("");
      if (code.length >= 8) return `${code.slice(0, 4)}-${code.slice(4, 8)}`;
    }
  } catch {
    /* fall through */
  }
  try {
    const chars = await page.evaluate(() => {
      const el = document.querySelector("[data-link-code]");
      if (!el) return "";
      return Array.from(el.children).map((c) => (c.textContent ?? "").trim()).join("");
    });
    if (chars.length === 8) return `${chars.slice(0, 4)}-${chars.slice(4)}`;
  } catch {
    /* fall through */
  }
  try {
    const text = await page.evaluate(() => document.body?.innerText ?? "");
    // Uppercase-only words with a digit or letter mix; ignore plain words like "WHATSAPP".
    for (const m of text.matchAll(new RegExp(CODE_RE, "g"))) {
      const c = m[0];
      if (/-/.test(c) || /\d/.test(c)) return c.includes("-") ? c : `${c.slice(0, 4)}-${c.slice(4)}`;
    }
    const spaced = text.split(/\s+/).filter((t) => /^[A-Z0-9]$/.test(t));
    if (spaced.length >= 8) return `${spaced.slice(0, 4).join("")}-${spaced.slice(4, 8).join("")}`;
  } catch {
    /* ignore */
  }
  return null;
}

/**
 * Drives WhatsApp Web's "Log in with phone number" flow; returns the 8-character
 * code, or null. Never throws — the screenshot shows the operator what happened.
 *
 * As seen 11 Oct 2026: the login card shows a QR first, and the "Log in with
 * phone number" link appears beside it once the QR has loaded. The next screen
 * has a country picker, one text field labelled "Type your phone number to log
 * in to WhatsApp" (pre-filled "+91 "), and Next.
 */
export async function startPhoneNumberLogin(page: Page, phoneE164: string, note: (step: string) => void = () => {}): Promise<string | null> {
  try {
    // The phone-number link appears beside the QR once the QR has loaded.
    const qr = await page.locator(LOGIN_SELECTOR).first().waitFor({ state: "visible", timeout: 20_000 }).then(() => true, () => false);
    note(qr ? "QR showing" : "no QR after 30 s");
    note(`phone-number links visible: ${await page.getByText(/log in with phone number|link with phone number/i).filter({ visible: true }).count()}`);
    await clickPhoneNumberLogin(page);
    note("clicked Log in with phone number");
    const input = page.locator('input[aria-label*="phone number" i], input[type="tel"]').filter({ visible: true }).first();
    await input.waitFor({ state: "visible", timeout: 8_000 });
    const typed = await typePhoneNumber(page, input, phoneE164);
    note(`typed the number (field now "${typed.value}")`);
    // A wrong number would ask some other phone for a code; the QR is the fallback.
    if (!typed.ok) {
      note("the field does not hold this number — not pressing Next");
      return null;
    }
    await page.waitForTimeout(500);
    const next = page.getByRole("button", { name: /^next$/i }).filter({ visible: true }).first();
    if (await next.isVisible().catch(() => false)) await next.click();
    else await input.press("Enter");
    note("pressed Next");
    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(1000);
      const code = await readLinkCode(page);
      if (code) return code;
    }
    note("no code on the page after 15 s");
  } catch (error) {
    note(`stopped: ${error instanceof Error ? error.message.split("\n")[0] : String(error)}`);
  }
  return null;
}

const digitsOf = (text: string) => text.replace(/\D/g, "");

/**
 * Types the number into the login form's phone field and checks it took.
 *
 * The field carries a country prefix the browser cannot delete ("+91 ", from
 * the IP), and typing the full international number after it doubles the
 * code: "+91 919876543210", in GoLogin's browser (23 Oct 2026). Right after
 * the form opens the prefix can still be a placeholder "+1 ", so it is given
 * a moment to settle, then only the digits after it are typed. Failing that,
 * fill() with the whole number, which the field parses itself.
 */
async function typePhoneNumber(page: Page, input: Locator, phoneE164: string): Promise<{ ok: boolean; value: string }> {
  const want = digitsOf(phoneE164);
  const value = () => input.inputValue().catch(() => "");
  const clear = async () => {
    await input.click();
    await input.press("ControlOrMeta+A");
    await input.press("Backspace");
  };
  await page.waitForTimeout(1500);
  await clear();
  const prefix = digitsOf(await value());
  if (prefix && want.startsWith(prefix)) {
    await input.pressSequentially(want.slice(prefix.length), { delay: 40 });
    if (digitsOf(await value()) === want) return { ok: true, value: await value() };
  }
  await clear();
  await input.fill(`+${want}`);
  const filled = await value();
  return { ok: digitsOf(filled) === want, value: filled };
}

/**
 * WhatsApp's "Log in with phone number". Two elements carry that text — the
 * link beside the QR and a visually hidden label ("Link with phone number
 * instead.") — and the first one matched timed out (23 Oct 2026). The real
 * control is tried first by role, then every visible match in turn.
 */
export async function clickPhoneNumberLogin(page: Page): Promise<void> {
  const name = /log in with phone number|link with phone number/i;
  const candidates = [
    page.getByRole("button", { name }),
    page.getByRole("link", { name }),
    page.getByText(name).filter({ visible: true }),
  ];
  for (const locator of candidates) {
    const count = await locator.count().catch(() => 0);
    for (let i = count - 1; i >= 0; i--) {
      if (await locator.nth(i).click({ timeout: 3_000 }).then(() => true, () => false)) return;
    }
  }
  throw new Error('no clickable "Log in with phone number"');
}

/**
 * Closes WhatsApp's one-off dialogs ("What's new on WhatsApp Web" after a new
 * link, 23 Oct 2026) that sit over the chats, so the extension's clicks reach
 * the chat and its Voice call button. Returns how many it closed.
 */
export async function dismissDialogs(page: Page): Promise<number> {
  let closed = 0;
  for (let i = 0; i < 3; i++) {
    const dialog = page.getByRole("dialog").filter({ visible: true }).first();
    if (!(await dialog.isVisible().catch(() => false))) break;
    const button = dialog.getByRole("button", { name: /^(continue|ok|got it|not now|close)$/i }).first();
    if (!(await button.click({ timeout: 2_000 }).then(() => true, () => false))) await page.keyboard.press("Escape");
    closed++;
    await page.waitForTimeout(500);
  }
  return closed;
}

/** From the phone-number form back to the QR ("Log in with QR code"), if the form is up. */
export async function backToQr(page: Page): Promise<void> {
  await page
    .getByText(/log in with qr code|link with qr code/i)
    .filter({ visible: true })
    .first()
    .click({ timeout: 3_000 })
    .catch(() => {});
}

export async function screenshotDataUrl(page: Page): Promise<string> {
  const buf = await page.screenshot({ type: "jpeg", quality: 60 });
  return `data:image/jpeg;base64,${buf.toString("base64")}`;
}
