/**
 * Shade, the AgentSDR mascot, as pixel data. Pure — no React, no CSS — so
 * the Mascot component, the static icon files (src/app/icon.svg,
 * apple-icon.png, the recorder extension's PNGs) and the launch video all
 * draw from this one source. Redraw them together if a frame changes here.
 *
 * '#' is a filled pixel. Every frame is 12 pixels wide and stands on the
 * floor at y = 11, so a taller frame rises instead of sinking; `dx` shifts a
 * frame sideways. VIEWBOX leaves a pixel of room for both.
 */

const BODY = [
  "....####....",
  "..########..",
  ".##########.",
  ".##..##..##.",
  ".##..##..##.",
  "############",
  "#####..#####",
  "############",
];
const LEG = "###..##..###";

/** The logo: standing, three straight legs. */
export const STAND = [...BODY, LEG, LEG, "##...##...##"];
const LIFT_L = [...BODY, LEG, LEG, ".....##...##"];
const LIFT_R = [...BODY, LEG, LEG, "##...##....."];
// On a lifted step the planted legs stretch a row, so the whole body rises.
const TALL_L = [...BODY, LEG, LEG, "##...##...##", ".....##...##"];
const TALL_R = [...BODY, LEG, LEG, "##...##...##", "##...##....."];
const PINCH = [...BODY, LEG, ".###.##.###.", "..##.##.##.."];

export type MascotFrame = { grid: string[]; dx?: number };
export type MascotCycle = "step" | "bounce" | "waddle" | "scuttle";

/** Each walk cycle: its frames in play order, and how long each frame holds. */
export const CYCLES: Record<MascotCycle, { frameMs: number; frames: MascotFrame[] }> = {
  /** Feet only. Calm enough to leave running. */
  step: { frameMs: 220, frames: [{ grid: STAND }, { grid: LIFT_L }, { grid: STAND }, { grid: LIFT_R }] },
  /** The body rises a pixel on each lifted step. Stroll walks with this one. */
  bounce: { frameMs: 190, frames: [{ grid: STAND }, { grid: TALL_L }, { grid: STAND }, { grid: TALL_R }] },
  /** Weight shifts a pixel to each side. */
  waddle: { frameMs: 230, frames: [{ grid: STAND }, { grid: LIFT_L, dx: 1 }, { grid: STAND }, { grid: LIFT_R, dx: -1 }] },
  /** Legs out, legs in, quickly. */
  scuttle: { frameMs: 120, frames: [{ grid: STAND }, { grid: PINCH }] },
};

/** Square, with room for a frame that rises or shifts a pixel. */
export const VIEWBOX = "-1 -1.5 14 14";
const FLOOR = 11;

export type PixelRun = { x: number; y: number; w: number };

/** A frame as horizontal runs of filled pixels, in VIEWBOX units. */
export function frameRuns({ grid, dx = 0 }: MascotFrame): PixelRun[] {
  const top = FLOOR - grid.length;
  const runs: PixelRun[] = [];
  grid.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      if (row[x] !== "#") continue;
      let end = x;
      while (row[end + 1] === "#") end++;
      runs.push({ x: x + dx, y: y + top, w: end - x + 1 });
      x = end;
    }
  });
  return runs;
}

/**
 * A frame as one SVG path: each run is a 1-unit-tall rectangle. One element per
 * frame instead of one per run keeps a page with many walking Shades light.
 */
export function framePath(frame: MascotFrame): string {
  return frameRuns(frame)
    .map((r) => `M${r.x} ${r.y}h${r.w}v1h-${r.w}z`)
    .join("");
}
