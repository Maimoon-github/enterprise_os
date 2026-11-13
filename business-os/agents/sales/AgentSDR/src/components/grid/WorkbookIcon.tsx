/**
 * The glyph for a workbook — the container the sheet tabs live in.
 *
 * Drawn as two stacked pages with a grid on the front one, so it reads as
 * "several tables in one file" and stays distinguishable from a single table
 * (SheetIcon) at 16px. Blue rather than SheetIcon's green for the same
 * reason: the two sit next to each other in every list and picker.
 *
 * Replaces RiNodeTree, which is a hierarchy/graph glyph and said nothing
 * about spreadsheets.
 */
export default function WorkbookIcon({ className = "size-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      {/* The sheet behind, peeking out top-right. */}
      <path
        d="M6 1.5h4.4c.2 0 .39.08.53.22l2.35 2.35c.14.14.22.33.22.53V11a.75.75 0 0 1-.75.75H6A.75.75 0 0 1 5.25 11V2.25A.75.75 0 0 1 6 1.5Z"
        fill="#93B4E8"
      />
      {/* The sheet in front. */}
      <path
        d="M3 4.25A.75.75 0 0 1 3.75 3.5h4.4c.2 0 .39.08.53.22l2.35 2.35c.14.14.22.33.22.53v7.15a.75.75 0 0 1-.75.75h-6.75A.75.75 0 0 1 3 13.75v-9.5Z"
        fill="#1A73E8"
      />
      <path d="M8.2 3.6v2.15c0 .28.22.5.5.5h2.15L8.2 3.6Z" fill="#0B4FA8" />
      <path
        d="M4.9 8.4h5.2M4.9 10.1h5.2M4.9 11.8h5.2M7.5 8.4v3.4"
        stroke="#fff"
        strokeWidth="0.85"
        strokeLinecap="round"
      />
    </svg>
  );
}
