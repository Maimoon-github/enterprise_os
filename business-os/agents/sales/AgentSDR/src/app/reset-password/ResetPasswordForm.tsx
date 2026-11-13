"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { authClient } from "@/lib/auth/client";
import { AuthShell } from "@/components/auth/AuthShell";
import { ErrorCallout, Field, InfoCallout, SubmitButton, linkClass } from "@/components/auth/fields";

export function ResetPasswordForm({ token, invalid }: { token: string | null; invalid: boolean }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) return setError("Password must be at least 8 characters.");
    if (password !== confirm) return setError("The passwords don't match.");
    if (!token) return;
    setLoading(true);
    const { error: err } = await authClient.resetPassword({ newPassword: password, token });
    setLoading(false);
    if (err) setError(err.code === "INVALID_TOKEN" ? "This reset link is invalid or has expired." : err.message || "Something went wrong. Please try again.");
    else setDone(true);
  }

  if (invalid) {
    return (
      <AuthShell title="Link expired" subtitle="This password reset link is invalid or has expired.">
        <Link href="/forgot-password" className={linkClass}>
          Request a new link
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Choose a new password">
      {done ? (
        <div className="flex flex-col gap-3">
          <InfoCallout>Your password has been updated.</InfoCallout>
          <Link href="/sign-in" className={linkClass}>
            Continue to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label="New password" type="password" autoComplete="new-password" minLength={8} required hint="At least 8 characters." value={password} onChange={(e) => setPassword(e.target.value)} />
          <Field label="Confirm password" type="password" autoComplete="new-password" minLength={8} required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          {error && <ErrorCallout>{error}</ErrorCallout>}
          <SubmitButton loading={loading} loadingLabel="Saving...">
            Update password
          </SubmitButton>
        </form>
      )}
    </AuthShell>
  );
}
