"use client";

import { useState } from "react";
import { RiArrowDownSLine, RiArrowUpSLine, RiDraggable } from "@remixicon/react";
import { getSearchUsage } from "@/lib/linkedin/searchLeadLimit";
import { LinkedInAccountTag } from "@/components/linkedin/LinkedInAccountTag";

export type SearchPickerAccount = {
  id: string;
  username: string;
  name: string | null;
  profilePictureUrl: string | null;
  searchLeadsToday: number;
  /** Leads this account may pull a day (Settings → LinkedIn → Sending rules). */
  searchLimit: number;
};

/**
 * Which accounts the last bulk/CSV run was restricted to. Kept per browser so the
 * same few accounts stay picked between visits without a server-side setting —
 * carried over from the old SearchQueueClient.
 */
export const RUN_ACCOUNTS_STORAGE_KEY = "linkedin.searchQueue.runAccountIds";

export function loadStoredRunAccountIds(): string[] | null {
  try {
    const raw = localStorage.getItem(RUN_ACCOUNTS_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.every((v) => typeof v === "string") ? parsed : null;
  } catch {
    return null;
  }
}

export function storeRunAccountIds(ids: string[]): void {
  try {
    localStorage.setItem(RUN_ACCOUNTS_STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // Private mode / blocked storage — the selection just won't be remembered.
  }
}

function QuotaLabel({ account }: { account: SearchPickerAccount }) {
  const usage = getSearchUsage(account.searchLeadsToday, account.searchLimit);
  return (
    <span className={`shrink-0 text-paragraph-xs tabular-nums ${usage.limitReached ? "text-warning-base" : "text-text-soft-400"}`}>
      {usage.limitReached ? "At limit · " : ""}
      {usage.used}/{usage.limit}
    </span>
  );
}

/**
 * Shared checkbox/radio list of connected LinkedIn accounts with daily search-quota
 * usage shown per account. Used by the "New search" dialog (CSV step, multi-select)
 * and the "Run" dialog on a search's detail page (multi-select), and the "New
 * search" single-search step (single-select).
 *
 * When `order`/`onReorder` are supplied (multi mode only), the selected accounts
 * are shown as a separate, draggable, ordered list above the plain checkbox list
 * of the rest — the order is meaningful to the caller (most-preferred first).
 */
export function SearchAccountPicker({
  accounts,
  selected,
  onToggle,
  mode = "multi",
  onSelectAll,
  onClear,
  order,
  onReorder,
}: {
  accounts: SearchPickerAccount[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  mode?: "single" | "multi";
  onSelectAll?: () => void;
  onClear?: () => void;
  order?: string[];
  onReorder?: (ids: string[]) => void;
}) {
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  const showOrdered = mode === "multi" && !!order && !!onReorder;

  const byId = new Map(accounts.map((a) => [a.id, a]));
  const orderedAccounts = showOrdered
    ? (order as string[]).map((id) => byId.get(id)).filter((a): a is SearchPickerAccount => !!a)
    : [];
  const orderedIds = new Set(orderedAccounts.map((a) => a.id));
  const restAccounts = showOrdered ? accounts.filter((a) => !orderedIds.has(a.id)) : accounts;

  function moveByStep(id: string, delta: number) {
    if (!order || !onReorder) return;
    const idx = order.indexOf(id);
    const newIdx = idx + delta;
    if (idx === -1 || newIdx < 0 || newIdx >= order.length) return;
    const next = [...order];
    [next[idx], next[newIdx]] = [next[newIdx], next[idx]];
    onReorder(next);
  }

  function handleDrop(targetId: string) {
    if (dragId && order && onReorder && dragId !== targetId) {
      const current = order.filter((id) => id !== dragId);
      const targetIndex = current.indexOf(targetId);
      if (targetIndex !== -1) {
        current.splice(targetIndex, 0, dragId);
        onReorder(current);
      }
    }
    setDragId(null);
    setOverId(null);
  }

  function renderCheckboxRow(a: SearchPickerAccount) {
    const checked = selected.has(a.id);
    const usage = getSearchUsage(a.searchLeadsToday, a.searchLimit);
    const disabled = mode === "single" && usage.limitReached;
    return (
      <li key={a.id}>
        <label
          className={
            disabled
              ? "flex cursor-not-allowed items-center gap-3 rounded-lg px-2 py-1.5 opacity-50"
              : "flex cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-bg-weak-50"
          }
        >
          <input
            type={mode === "single" ? "radio" : "checkbox"}
            name={mode === "single" ? "search-account" : undefined}
            checked={checked}
            disabled={disabled}
            onChange={() => onToggle(a.id)}
            className="size-4 shrink-0 rounded accent-primary-base"
          />
          <span className="min-w-0 flex-1">
            <LinkedInAccountTag account={a} />
          </span>
          <QuotaLabel account={a} />
        </label>
      </li>
    );
  }

  return (
    <div>
      {mode === "multi" && (onSelectAll || onClear) && (
        <div className="mb-2 flex items-center justify-between text-paragraph-xs">
          <span className="text-text-soft-400">
            {selected.size} of {accounts.length} selected
          </span>
          <div className="flex gap-3">
            {onSelectAll && (
              <button type="button" className="text-text-sub-600 hover:text-text-strong-950" onClick={onSelectAll}>
                Select all
              </button>
            )}
            {onClear && (
              <button type="button" className="text-text-sub-600 hover:text-text-strong-950" onClick={onClear}>
                Clear
              </button>
            )}
          </div>
        </div>
      )}
      {accounts.length === 0 ? (
        <p className="text-paragraph-sm text-text-soft-400">No connected accounts</p>
      ) : showOrdered ? (
        <div className="space-y-3">
          <div>
            <p className="mb-1 text-label-xs text-text-soft-400">Order — the first account is used first</p>
            {orderedAccounts.length === 0 ? (
              <p className="text-paragraph-sm text-text-soft-400">No accounts selected</p>
            ) : (
              <ul className="space-y-1">
                {orderedAccounts.map((a, i) => {
                  const isDragging = dragId === a.id;
                  const isOver = overId === a.id && dragId !== null && dragId !== a.id;
                  return (
                    <li
                      key={a.id}
                      draggable
                      onDragStart={() => setDragId(a.id)}
                      onDragOver={(e) => {
                        e.preventDefault();
                        if (overId !== a.id) setOverId(a.id);
                      }}
                      onDrop={(e) => {
                        e.preventDefault();
                        handleDrop(a.id);
                      }}
                      onDragEnd={() => {
                        setDragId(null);
                        setOverId(null);
                      }}
                      className={[
                        "flex items-center gap-2 rounded-lg border px-2 py-1.5 transition",
                        isDragging ? "opacity-40" : "",
                        isOver ? "border-primary-base ring-2 ring-primary-base" : "border-transparent",
                      ].join(" ")}
                    >
                      <span className="cursor-grab text-text-soft-400 active:cursor-grabbing">
                        <RiDraggable className="h-4 w-4 shrink-0" />
                      </span>
                      <span className="w-4 shrink-0 text-label-xs tabular-nums text-text-soft-400">{i + 1}</span>
                      <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
                        <input
                          type="checkbox"
                          checked
                          onChange={() => onToggle(a.id)}
                          className="size-4 shrink-0 rounded accent-primary-base"
                        />
                        <LinkedInAccountTag account={a} />
                      </label>
                      <QuotaLabel account={a} />
                      <div className="flex shrink-0 flex-col">
                        <button
                          type="button"
                          aria-label="Move up"
                          disabled={i === 0}
                          onClick={() => moveByStep(a.id, -1)}
                          className="text-text-soft-400 hover:text-text-strong-950 disabled:cursor-not-allowed disabled:opacity-30"
                        >
                          <RiArrowUpSLine className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          aria-label="Move down"
                          disabled={i === orderedAccounts.length - 1}
                          onClick={() => moveByStep(a.id, 1)}
                          className="text-text-soft-400 hover:text-text-strong-950 disabled:cursor-not-allowed disabled:opacity-30"
                        >
                          <RiArrowDownSLine className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
          {restAccounts.length > 0 && (
            <div>
              <p className="mb-1 text-label-xs text-text-soft-400">Not used</p>
              <ul className="max-h-56 space-y-1 overflow-y-auto">{restAccounts.map((a) => renderCheckboxRow(a))}</ul>
            </div>
          )}
        </div>
      ) : (
        <ul className="max-h-72 space-y-1 overflow-y-auto">{accounts.map((a) => renderCheckboxRow(a))}</ul>
      )}
    </div>
  );
}
