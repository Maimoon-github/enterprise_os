"use client";

import type { IntegrationDefinition } from "@/lib/integrations/types";

function faviconUrl(websiteUrl: string): string {
  try {
    const { hostname } = new URL(websiteUrl);
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(hostname)}&sz=64`;
  } catch {
    return "";
  }
}

export default function IntegrationIcon({
  integration,
  size = 28,
  className = "",
}: {
  integration: IntegrationDefinition;
  size?: number;
  className?: string;
}) {
  const fallbackSrc = faviconUrl(integration.websiteUrl);

  return (
    <span
      className={`relative flex shrink-0 items-center justify-center overflow-hidden rounded-md font-bold text-slate-900 ${className}`}
      style={{
        width: size,
        height: size,
        backgroundColor: integration.iconBackground,
        fontSize: Math.max(9, Math.round(size * 0.45)),
      }}
      title={integration.name}
    >
      {integration.iconText}
      {fallbackSrc && (
        // Hiding a failed favicon reveals the catalog's letter fallback.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={fallbackSrc}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          className="absolute inset-0 size-full bg-white object-contain"
          onError={(event) => {
            event.currentTarget.style.display = "none";
          }}
        />
      )}
      {integration.iconUrl && (
        // The provider SVG sits above the favicon. A failed SVG is hidden so
        // the favicon remains visible, and its own failure reveals iconText.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={integration.iconUrl}
          alt=""
          loading="lazy"
          className="absolute inset-0 size-full bg-white object-contain"
          onError={(event) => {
            event.currentTarget.style.display = "none";
          }}
        />
      )}
    </span>
  );
}
