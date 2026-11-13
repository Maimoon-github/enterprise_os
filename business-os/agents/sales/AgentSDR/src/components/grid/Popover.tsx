"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/**
 * A panel anchored under its trigger, closed by outside click or Escape.
 *
 * Shared by the columns, filter, sort and search popovers so the anchoring and
 * dismissal rules stay identical between them — Clay's toolbar panels all
 * behave the same way, and four hand-rolled copies would drift.
 */
export default function Popover({
  anchorRect,
  onClose,
  children,
  width = 420,
  align = "left",
}: {
  anchorRect: DOMRect | null;
  onClose: () => void;
  children: React.ReactNode;
  width?: number;
  align?: "left" | "right";
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: effect resets/seeds local state when props or open state change; deriving during render would change timing
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!anchorRect) return;

    // Pointerdown rather than click: a click listener fires after the trigger's
    // own onClick, which would immediately reopen the panel it just closed.
    // A Radix list opened from inside the panel (an AlignUI Select) is
    // portaled to <body>, so picking from it lands outside `ref` — and its
    // Escape is already spent closing that list, which Radix marks with
    // preventDefault. Neither should close the panel too.
    const onDown = (e: PointerEvent) => {
      const target = e.target as Element;
      if (target.closest?.("[data-radix-popper-content-wrapper]")) return;
      // While a Radix Select closes it keeps `pointer-events: none` on <body>,
      // so the next click lands on <html> itself. A real outside click always
      // hits some element on the page; this one is the person still working
      // inside the panel (picking the operator after the column).
      if (target === document.documentElement || target === document.body) return;
      if (ref.current && !ref.current.contains(target)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented) onClose();
    };

    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [anchorRect, onClose]);

  if (!anchorRect || !mounted) return null;

  const left =
    align === "right"
      ? Math.max(8, anchorRect.right - width)
      : Math.min(anchorRect.left, window.innerWidth - width - 8);

  const gap = 6;
  const viewportPadding = 8;
  const spaceBelow = window.innerHeight - anchorRect.bottom - gap - viewportPadding;
  const spaceAbove = anchorRect.top - gap - viewportPadding;
  const opensUpward = spaceBelow < 240 && spaceAbove > spaceBelow;
  const maxHeight = Math.max(80, opensUpward ? spaceAbove : spaceBelow);
  const top = opensUpward
    ? anchorRect.top - gap - maxHeight
    : anchorRect.bottom + gap;

  return createPortal(
    <div
      ref={ref}
      style={{ top, left, width, maxHeight }}
      className="fixed z-50 overflow-y-auto overscroll-contain rounded-xl border border-stroke-soft-200 bg-bg-white-0 shadow-[0_12px_32px_-8px_rgba(15,23,42,0.18)]"
    >
      {children}
    </div>,
    document.body,
  );
}
