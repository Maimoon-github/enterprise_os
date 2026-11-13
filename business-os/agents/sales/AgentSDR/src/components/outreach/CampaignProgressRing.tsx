import { RiCheckLine } from "@remixicon/react";

const SIZE = 40;
const STROKE = 3;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * Row leading indicator: a ring filled to the campaign's sequence-completion
 * share. A finished campaign collapses to a solid check instead of "100%",
 * which reads faster when scanning a long list.
 */
export default function CampaignProgressRing({
  progress,
  complete,
}: {
  /** 0–1, or null when the campaign has no leads to progress through. */
  progress: number | null;
  complete: boolean;
}) {
  if (complete) {
    return (
      <div className="flex size-10 shrink-0 items-center justify-center rounded-full ring-2 ring-inset ring-primary-base">
        <RiCheckLine className="size-5 text-primary-base" />
      </div>
    );
  }

  // No leads means there is nothing to progress through — an em dash reads more
  // honestly than "0%", which implies work that has stalled.
  if (progress === null) {
    return (
      <div className="flex size-10 shrink-0 items-center justify-center rounded-full ring-2 ring-inset ring-bg-soft-200">
        <span className="text-label-xs text-text-soft-400">—</span>
      </div>
    );
  }

  const pct = Math.round(progress * 100);
  const offset = CIRCUMFERENCE * (1 - progress);

  return (
    <div className="relative size-10 shrink-0">
      <svg width={SIZE} height={SIZE} className="-rotate-90" aria-hidden="true">
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          strokeWidth={STROKE}
          className="stroke-bg-soft-200"
        />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          className="stroke-success-base transition-[stroke-dashoffset] duration-500 ease-out"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-label-xs text-text-strong-950">
        {pct}%
      </span>
    </div>
  );
}
