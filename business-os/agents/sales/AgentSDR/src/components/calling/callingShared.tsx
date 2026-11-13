"use client";

import { useEffect, useState } from "react";
import { RiSparklingLine } from "@remixicon/react";
import * as Badge from "@/components/alignui/badge";
import { ClassificationPicker } from "@/components/crm/ActionRowTools";
import { errorMessage } from "@/components/crm/crm-utils";
import { listCrmCategories, setLeadStage } from "@/lib/calls/client";
import {
  type CallCampaignStatus,
  CONTACT_CALL_STATUS_DEFINITIONS,
  RETRY_AFTER_DAYS,
  type CampaignContact,
  type ContactCallStatus,
  type LeadStageCategory,
} from "@/lib/calls/contract";
import { cn } from "@/utils/cn";

/** Total calls the retry schedule allows before a lead is done: the first plus one per retry step, plus the last unanswered one. */
export const MAX_UNANSWERED_ATTEMPTS = RETRY_AFTER_DAYS.length + 1;

/** Where the lead is in the calling flow, spelled out; the colour only reinforces it. */
export function CallStatusBadge({ status }: { status: ContactCallStatus }) {
  const definition = CONTACT_CALL_STATUS_DEFINITIONS[status];
  return (
    <Badge.Root variant="lighter" size="medium" color={definition.tone} className="shrink-0 whitespace-nowrap">
      <Badge.Dot />
      {definition.label}
    </Badge.Root>
  );
}

/** Active / Paused, as the campaign list and the campaign page show it. */
export function CampaignStatusBadge({ status }: { status: CallCampaignStatus }) {
  const paused = status === "paused";
  return (
    <Badge.Root variant="lighter" size="medium" color={paused ? "orange" : "green"} className="shrink-0">
      <Badge.Dot />
      {paused ? "Paused" : "Active"}
    </Badge.Root>
  );
}

/** "Attempt 2 of 4", for statuses that count toward the retry schedule. */
export function attemptHint(contact: Pick<CampaignContact, "callStatus" | "unansweredAttempts">): string | null {
  if (contact.callStatus !== "no_answer" && contact.callStatus !== "busy") return null;
  if (contact.unansweredAttempts <= 0) return null;
  return `attempt ${Math.min(contact.unansweredAttempts, MAX_UNANSWERED_ATTEMPTS)} of ${MAX_UNANSWERED_ATTEMPTS}`;
}

/** The company's favicon; one that fails to load is dropped, not left broken. */
export function CompanyFavicon({ domain, className }: { domain: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  // eslint-disable-next-line @next/next/no-img-element -- remote favicon service, sized by CSS
  return <img src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=32`} alt="" className={cn("size-3.5 shrink-0 rounded-sm", className)} onError={() => setFailed(true)} />;
}

export function bareDomain(website: string): string {
  return website.replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/\/.*$/, "");
}

let categoriesCache: Promise<Record<string, unknown>[]> | null = null;

/** The CRM's categories, fetched once per page load and shared by every picker. */
export function useCrmCategories(): Record<string, unknown>[] {
  const [categories, setCategories] = useState<Record<string, unknown>[]>([]);
  useEffect(() => {
    let active = true;
    categoriesCache ??= listCrmCategories().catch((cause) => {
      categoriesCache = null;
      throw cause;
    });
    categoriesCache.then((next) => { if (active) setCategories(next); }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  return categories;
}

/**
 * The lead's CRM stage as a picker — the CRM's own ClassificationPicker, so it
 * looks and groups exactly like the CRM's. A pick calls setLeadStage and hands
 * the updated contact back so the row can be replaced in place.
 */
export function LeadStagePicker({
  contact,
  categories,
  compact,
  onUpdated,
}: {
  contact: CampaignContact;
  categories: Record<string, unknown>[];
  compact?: boolean;
  onUpdated: (contact: CampaignContact) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const crm = contact.crm;
  const byModel = crm?.categorySource === "integration" || crm?.categorySource === "ai";

  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5">
        <ClassificationPicker
          compact={compact}
          categories={categories}
          categoryKey={crm?.categoryKey ?? null}
          subcategoryId={crm?.subcategoryId ?? null}
          subcategoryName={crm?.subcategoryName ?? null}
          disabled={busy}
          onChange={async (choice) => {
            setBusy(true);
            setError("");
            try {
              onUpdated(await setLeadStage(contact.id, {
                categoryKey: choice.categoryKey as LeadStageCategory,
                subcategoryId: choice.subcategoryId,
              }));
            } catch (cause) {
              setError(errorMessage(cause));
            } finally {
              setBusy(false);
            }
          }}
        />
        {byModel && crm?.categoryKey && (
          <span title="Set by the AI from the call transcript" className={cn("inline-flex h-5 shrink-0 items-center gap-0.5 rounded px-1 text-label-xs text-feature-dark ring-1 ring-inset ring-feature-light bg-feature-lighter")}>
            <RiSparklingLine className="size-3" aria-hidden="true" />AI
          </span>
        )}
      </div>
      {error && <p role="alert" className="mt-1 text-paragraph-xs text-error-dark">{error}</p>}
    </div>
  );
}

const AVATAR_TONES = [
  "bg-information-lighter text-information-dark",
  "bg-success-lighter text-success-dark",
  "bg-warning-lighter text-warning-dark",
  "bg-error-lighter text-error-dark",
  "bg-feature-lighter text-feature-dark",
  "bg-verified-lighter text-verified-dark",
  "bg-away-lighter text-away-dark",
  "bg-stable-lighter text-stable-dark",
];

function initialsOf(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const first = Array.from(words[0])[0] ?? "?";
  const last = words.length > 1 ? (Array.from(words[words.length - 1])[0] ?? "") : "";
  return (first + last).toUpperCase();
}

function toneFor(name: string): string {
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.codePointAt(0)!) >>> 0;
  return AVATAR_TONES[hash % AVATAR_TONES.length];
}

/** A round avatar: the photo when there is one and it loads, otherwise initials on a colour derived from the name. */
export function Avatar({ name, src, className }: { name: string; src?: string | null; className?: string }) {
  // Keyed by the URL, so a new photo gets a fresh chance after one failed.
  return <AvatarInner key={src ?? ""} name={name} src={src} className={className} />;
}

function AvatarInner({ name, src, className }: { name: string; src?: string | null; className?: string }) {
  const [failed, setFailed] = useState(false);
  const base = "inline-flex size-8 shrink-0 select-none items-center justify-center overflow-hidden rounded-full";
  if (src && !failed) {
    // eslint-disable-next-line @next/next/no-img-element -- remote or uploaded photo, sized by CSS
    return <img src={src} alt="" className={cn(base, "object-cover", className)} onError={() => setFailed(true)} referrerPolicy="no-referrer" />;
  }
  return <span aria-hidden="true" className={cn(base, "text-label-xs", toneFor(name), className)}>{initialsOf(name)}</span>;
}

/** "Title @ Company", or whichever half exists; null when neither. */
export function titleAtCompany(person: { title: string | null; companyName: string | null }): string | null {
  const title = person.title?.trim();
  const company = person.companyName?.trim();
  if (title && company) return `${title} @ ${company}`;
  return title || company || null;
}

/** The follow-up date compactly: "Due today", "Due tomorrow", "Due in 3 days", or "Overdue · 12 Sep" (overdue: true). */
export function followUpHint(
  contact: Pick<CampaignContact, "stage" | "followUpAt">,
  now = new Date(),
): { text: string; overdue: boolean } | null {
  if (!contact.followUpAt || contact.stage === "done") return null;
  const due = new Date(contact.followUpAt);
  if (Number.isNaN(due.getTime())) return null;
  const day = (date: Date) => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  const days = Math.round((day(due) - day(now)) / 86_400_000);
  if (days < 0) {
    const short = due.toLocaleDateString(undefined, { day: "numeric", month: "short" });
    return { text: `Overdue \u00b7 ${short}`, overdue: true };
  }
  if (days === 0) return { text: "Due today", overdue: false };
  if (days === 1) return { text: "Due tomorrow", overdue: false };
  return { text: `Due in ${days} days`, overdue: false };
}
