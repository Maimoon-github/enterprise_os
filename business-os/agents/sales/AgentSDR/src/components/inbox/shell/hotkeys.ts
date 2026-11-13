"use client";

import { useEffect, useRef, type RefObject } from "react";

/** Below this width the inbox shows one pane at a time (Tailwind's `md`). */
const SINGLE_PANE_QUERY = "(max-width: 767px)";

function isEditable(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) return false;
  return element.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(element.tagName);
}

function visibleRows(list: HTMLElement): HTMLElement[] {
  return [...list.querySelectorAll<HTMLElement>("[data-inbox-row]")].filter((row) => row.offsetParent !== null);
}

/**
 * Keyboard triage for a split-pane inbox:
 *
 * - `j` / `k` move focus down / up the conversation list from anywhere that
 *   is not a text field; ↓ / ↑ do the same while focus is in the list (so
 *   the arrows still scroll an open thread).
 * - Enter opens the focused row — rows are buttons, so that is native.
 * - Esc leaves the thread: on a phone it closes it (back to the list), on a
 *   wide screen it returns focus to the open row in the list.
 *
 * Moving focus never opens a conversation: opening marks it read.
 */
export function useInboxHotkeys({ listRef, onClose }: { listRef: RefObject<HTMLElement | null>; onClose?: (() => void) | null }) {
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      // Menus, selects and dialogs own their keys.
      if (target?.closest?.('[role="dialog"],[role="alertdialog"],[role="menu"],[role="listbox"],[role="tablist"]')) return;
      const list = listRef.current;

      if (event.key === "Escape") {
        if (isEditable(target) || !closeRef.current) return;
        if (window.matchMedia(SINGLE_PANE_QUERY).matches) {
          closeRef.current();
          return;
        }
        const current = list?.querySelector<HTMLElement>('[data-inbox-row][aria-current="true"]');
        current?.focus();
        return;
      }

      if (isEditable(target) || !list) return;
      const letter = event.key === "j" || event.key === "k";
      const arrow = event.key === "ArrowDown" || event.key === "ArrowUp";
      if (!letter && !arrow) return;
      const inList = target ? list.contains(target) : false;
      if (arrow && !inList) return;

      const rows = visibleRows(list);
      if (rows.length === 0) return;
      event.preventDefault();
      const step = event.key === "j" || event.key === "ArrowDown" ? 1 : -1;
      const from = inList
        ? rows.findIndex((row) => row === target || row.contains(target))
        : rows.findIndex((row) => row.getAttribute("aria-current") === "true");
      const next = from < 0 ? (step > 0 ? 0 : rows.length - 1) : Math.min(rows.length - 1, Math.max(0, from + step));
      rows[next].focus();
      rows[next].scrollIntoView({ block: "nearest" });
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [listRef]);
}
