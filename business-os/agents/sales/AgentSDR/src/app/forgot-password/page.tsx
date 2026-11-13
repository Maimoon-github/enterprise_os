"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { authClient } from "@/lib/auth/client";
import { AuthShell } from "@/components/auth/AuthShell";
import { Field, InfoCallout, SubmitButton, linkClass } from "@/components/auth/fields";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    // The outcome is never shown, so the page can't be used to probe which emails have accounts.
    await authClient.requestPasswordReset({ email, redirectTo: "/reset-password" }).catch(() => null);
    setLoading(false);
    setDone(true);
  }

  return (
    <AuthShell
      title="Reset your password"
      subtitle="We'll email you a link to choose a new one"
      footer={
        <Link href="/sign-in" className={linkClass}>
          Back to sign in
        </Link>
      }
    >
      {done ? (
        <InfoCallout>If an account exists for {email}, we sent a link to reset your password.</InfoCallout>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <SubmitButton loading={loading} loadingLabel="Sending...">
            Send reset link
          </SubmitButton>
        </form>
      )}
    </AuthShell>
  );
}
