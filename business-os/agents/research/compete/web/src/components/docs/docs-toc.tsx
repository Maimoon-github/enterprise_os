"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

type TocItem = { id: string; label: string };

/**
 * Sticky table of contents with scrollspy. The link for the section currently
 * in view is highlighted, and a sliding indicator bar glides between entries
 * for a smooth, seamless transition as the reader scrolls.
 */
export function DocsToc({ items }: { items: TocItem[] }) {
  const [activeId, setActiveId] = useState(items[0]?.id ?? "");
  const linkRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const [indicator, setIndicator] = useState({ top: 0, height: 0, ready: false });

  // Track which section is in view.
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveId(visible[0].target.id);
      },
      // Activate a section once it reaches the upper third of the viewport.
      { rootMargin: "-30% 0px -60% 0px", threshold: 0 },
    );

    items.forEach((it) => {
      const el = document.getElementById(it.id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [items]);

  // Move the indicator bar to the active link.
  useEffect(() => {
    const el = linkRefs.current[activeId];
    if (el) setIndicator({ top: el.offsetTop, height: el.offsetHeight, ready: true });
  }, [activeId]);

  return (
    <nav aria-label="Table of contents" className="hidden lg:block">
      <div className="sticky top-24">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
          Contents
        </p>
        <ul className="relative mt-4 space-y-1 border-l border-border">
          <span
            aria-hidden
            className={cn(
              "absolute left-0 w-0.5 rounded-full bg-primary transition-all duration-300 ease-out",
              indicator.ready ? "opacity-100" : "opacity-0",
            )}
            style={{ top: indicator.top, height: indicator.height }}
          />
          {items.map((t, i) => {
            const active = t.id === activeId;
            return (
              <li key={t.id}>
                <a
                  ref={(el) => {
                    linkRefs.current[t.id] = el;
                  }}
                  href={`#${t.id}`}
                  onClick={() => setActiveId(t.id)}
                  aria-current={active ? "true" : undefined}
                  className={cn(
                    "block py-1 pl-4 text-sm transition-colors duration-300 ease-out",
                    active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "mr-2 font-mono text-xs transition-colors duration-300 ease-out",
                      active ? "text-primary" : "text-muted-foreground/60",
                    )}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  {t.label}
                </a>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
