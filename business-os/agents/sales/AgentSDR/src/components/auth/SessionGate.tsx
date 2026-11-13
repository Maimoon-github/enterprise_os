"use client";

import { useEffect, useState } from "react";
import { RiRefreshLine } from "@remixicon/react";
import { useSession } from "@/lib/auth/client";

/**
 * Keeps the signed-in frame honest in the browser: a visitor whose session
 * has ended goes to /sign-in, and a signed-in user with no active
 * organization goes to /onboarding. Navigation is a full load, so no
 * client-side cache from another session or organization survives it.
 *
 * This is convenience, not security — every API route and server page
 * checks the session and organization itself (src/lib/auth/context.ts).
 *
 * Two guards against a reload loop (seen on the public demo on iPhone, where
 * the page rendered and then bounced through sign-in forever):
 * - only the server saying "no session" sends the visitor away; a session
 *   check that failed (network, a proxy's challenge page) is not that;
 * - a third bounce within 30 seconds stops and says so instead.
 */
const BOUNCES_KEY = "agentsdr:session-gate-bounces";
const BOUNCE_WINDOW_MS = 30_000;
const MAX_BOUNCES = 3;

/** Records a redirect; false when this tab has already bounced too often to try again. */
function mayBounce(): boolean {
  try {
    const now = Date.now();
    const recent = (JSON.parse(window.sessionStorage.getItem(BOUNCES_KEY) ?? "[]") as number[]).filter((t) => now - t < BOUNCE_WINDOW_MS);
    if (recent.length >= MAX_BOUNCES) return false;
    window.sessionStorage.setItem(BOUNCES_KEY, JSON.stringify([...recent, now]));
    return true;
  } catch {
    // No storage (private mode): no loop guard, same as before.
    return true;
  }
}

export function SessionGate({ children }: { children: React.ReactNode }) {
  const { data, isPending, error } = useSession();
  const [stuck, setStuck] = useState(false);

  useEffect(() => {
    if (isPending || error) return;
    let target: string | null = null;
    if (!data) {
      const from = `${window.location.pathname}${window.location.search}`;
      target = `/sign-in?from=${encodeURIComponent(from)}`;
    } else if (!data.session.activeOrganizationId) {
      target = "/onboarding";
    }
    if (!target) {
      // Signed in and settled: the next bounce starts a fresh count.
      try {
        window.sessionStorage.removeItem(BOUNCES_KEY);
      } catch {}
      return;
    }
    if (mayBounce()) {
      window.location.replace(target);
      return;
    }
    const timer = window.setTimeout(() => setStuck(true), 0);
    return () => window.clearTimeout(timer);
  }, [data, isPending, error]);

  if (stuck) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-white-0 p-6">
        <div className="max-w-sm text-center">
          <p className="text-label-md text-text-strong-950">We couldn&apos;t keep you signed in</p>
          <p className="mt-2 text-paragraph-sm text-text-sub-600">
            This browser doesn&apos;t seem to keep this site&apos;s sign-in cookie. Allow cookies for this site, or open it in another browser.
          </p>
          <button
            type="button"
            onClick={() => {
              try {
                window.sessionStorage.removeItem(BOUNCES_KEY);
              } catch {}
              window.location.reload();
            }}
            className="mt-5 inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-label-sm text-text-strong-950 ring-1 ring-inset ring-stroke-soft-200 transition hover:bg-bg-weak-50"
          >
            <RiRefreshLine className="size-4" />
            Try again
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
