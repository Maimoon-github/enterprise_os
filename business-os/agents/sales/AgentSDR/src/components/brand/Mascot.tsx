import type { CSSProperties } from "react";
import { cn } from "@/utils/cn";
import { CYCLES, STAND, VIEWBOX, framePath, type MascotCycle, type MascotFrame } from "./mascotFrames";
import styles from "./mascot.module.css";

/**
 * Shade in currentColor. With no `cycle` it stands still (the logo). With
 * one it walks: `play="always"` loops, `play="hover"` walks only while the
 * nearest `.group` ancestor is hovered or focused, and stands otherwise.
 */
export function Mascot({
  className,
  cycle,
  play = "always",
}: {
  className?: string;
  cycle?: MascotCycle;
  play?: "always" | "hover";
}) {
  const frames: MascotFrame[] = cycle ? CYCLES[cycle].frames : [{ grid: STAND }];
  const ms = cycle ? CYCLES[cycle].frameMs : 0;
  const n = frames.length;
  return (
    <svg
      viewBox={VIEWBOX}
      fill="currentColor"
      aria-hidden="true"
      className={cn(styles.mascot, cycle && (play === "hover" ? styles.hover : styles.always), cycle && (n === 2 ? styles.n2 : styles.n4), className)}
      style={cycle ? ({ "--cycle": `${n * ms}ms` } as CSSProperties) : undefined}
    >
      {frames.map((frame, i) => (
        <path key={i} d={framePath(frame)} className={cycle ? styles.frame : undefined} style={cycle ? ({ "--delay": `${-((n - i) % n) * ms}ms` } as CSSProperties) : undefined} />
      ))}
    </svg>
  );
}

/**
 * Shade bouncing across its container, entering at the left edge and leaving
 * at the right; size and colour it with `walkerClassName`. Its feet rest on
 * the container's bottom edge, so a bottom border becomes the floor.
 */
export function MascotStroll({ className, walkerClassName, seconds = 36 }: { className?: string; walkerClassName?: string; seconds?: number }) {
  return (
    <div aria-hidden="true" className={cn(styles.stroll, className)}>
      <span className={cn(styles.walker, walkerClassName)} style={{ "--stroll": `${seconds}s` } as CSSProperties}>
        {/* The viewBox keeps 1.5 of its 14 units under the feet; drop them onto the floor. */}
        <Mascot cycle="bounce" className="size-full translate-y-[10.7%]" />
      </span>
    </div>
  );
}
