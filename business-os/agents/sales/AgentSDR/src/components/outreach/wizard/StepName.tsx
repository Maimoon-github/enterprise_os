"use client";

import { useState } from "react";
import Link from "next/link";
import { RiArrowRightLine, RiInformationLine, RiMailLine } from "@remixicon/react";

import * as Button from "@/components/alignui/button";
import * as Input from "@/components/alignui/input";

export default function StepName({
  campaignId,
  name,
  onNameChange,
  onContinue,
}: {
  campaignId: string | null;
  name: string;
  onNameChange: (name: string) => void;
  onContinue: (campaignId: string) => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleContinue() {
    if (!name.trim()) {
      setError("Give your campaign a name");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(
        campaignId ? `/api/outreach/campaigns/${campaignId}` : "/api/outreach/campaigns",
        {
          method: campaignId ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        },
      );
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Failed to create campaign");
        return;
      }
      onContinue(campaignId ?? data.campaign.id);
    } catch {
      setError("Could not save the campaign. Check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex size-11 items-center justify-center rounded-xl bg-primary-alpha-10 text-primary-base">
        <RiMailLine className="size-5" />
      </div>
      <h2 className="mt-5 text-title-h5 text-text-strong-950">Name your campaign</h2>
      <p className="mt-1 text-paragraph-sm text-text-sub-600">Use a clear internal name so your team can find it later.</p>

      <div className="mt-7 rounded-2xl bg-bg-white-0 p-5 ring-1 ring-inset ring-stroke-soft-200">
        <label htmlFor="campaign-name" className="mb-1.5 block text-label-sm text-text-strong-950">Campaign name</label>
        <Input.Root hasError={Boolean(error)}>
          <Input.Wrapper>
            <Input.Input
              id="campaign-name"
              autoFocus
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleContinue()}
              placeholder="e.g. Q3 Enterprise Outbound"
            />
          </Input.Wrapper>
        </Input.Root>
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-bg-weak-50 px-3 py-2.5 text-paragraph-xs text-text-sub-600">
          <RiInformationLine className="mt-0.5 size-4 shrink-0 text-text-soft-400" />
          A draft is saved when you continue. Going back edits the same draft instead of creating another campaign.
        </div>
        {error && <p className="mt-2 text-paragraph-xs text-error-base">{error}</p>}
      </div>

      <div className="mt-8 flex items-center justify-between border-t border-stroke-soft-200 pt-5">
        <Button.Root asChild variant="neutral" mode="ghost" size="medium">
          <Link href="/outreach/campaigns">Cancel</Link>
        </Button.Root>
        <Button.Root onClick={() => void handleContinue()} disabled={submitting || !name.trim()}>
          {submitting ? (campaignId ? "Saving…" : "Creating…") : "Continue"}
          <Button.Icon as={RiArrowRightLine} />
        </Button.Root>
      </div>
    </div>
  );
}
