"use client";

import { useState } from "react";
import { cn } from "@/utils/cn";

/**
 * A contact's LinkedIn picture when one is stored, their initials otherwise.
 * licdn URLs are signed and expire, so a picture that no longer loads falls
 * back to the initials too instead of leaving a broken image in the row.
 * Size and fallback colours come from `className` so each site keeps its own.
 */
export function ContactAvatar({ src, fallback, className }: { src?: string | null; fallback: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (src && !failed) {
    // eslint-disable-next-line @next/next/no-img-element -- remote CDN, sized by CSS; not worth the next/image allowlist
    return <img src={src} alt="" className={cn("shrink-0 rounded-full object-cover", className)} onError={() => setFailed(true)} />;
  }
  return <span className={cn("flex shrink-0 items-center justify-center rounded-full", className)}>{fallback}</span>;
}
