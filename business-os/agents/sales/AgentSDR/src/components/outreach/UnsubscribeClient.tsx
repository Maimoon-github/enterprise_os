"use client";

import { useState } from "react";

export default function UnsubscribeClient({ token }: { token: string | null }) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [email, setEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUnsubscribe() {
    if (!token) return;
    setState("loading");
    try {
      const res = await fetch("/api/outreach/unsubscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong");
        setState("error");
        return;
      }
      setEmail(data.email);
      setState("done");
    } catch {
      setError("Network error — please try again");
      setState("error");
    }
  }

  if (!token) {
    return (
      <div className="text-center">
        <h1 className="text-lg font-bold text-text-strong-950">Invalid link</h1>
        <p className="text-sm text-text-strong-950/50 mt-2">This unsubscribe link is missing its token.</p>
      </div>
    );
  }

  if (state === "done") {
    return (
      <div className="text-center">
        <div className="w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
          <svg className="w-6 h-6 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        </div>
        <h1 className="text-lg font-bold text-text-strong-950">You&apos;re unsubscribed</h1>
        <p className="text-sm text-text-strong-950/50 mt-2">
          {email} won&apos;t receive any further emails from us.
        </p>
      </div>
    );
  }

  return (
    <div className="text-center">
      <h1 className="text-lg font-bold text-text-strong-950">Unsubscribe</h1>
      <p className="text-sm text-text-strong-950/50 mt-2 mb-6">
        Click below to stop receiving emails from this sender.
      </p>
      {error && <p className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 rounded-lg px-3 py-2 mb-4">{error}</p>}
      <button
        onClick={handleUnsubscribe}
        disabled={state === "loading"}
        className="w-full h-10 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 transition-colors"
      >
        {state === "loading" ? "Unsubscribing…" : "Unsubscribe me"}
      </button>
    </div>
  );
}
