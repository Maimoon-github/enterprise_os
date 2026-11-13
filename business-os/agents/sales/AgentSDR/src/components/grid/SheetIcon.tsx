/**
 * The glyph for a table/sheet across the grid UI.
 *
 * Drawn rather than pulled from Remix so it reads like a spreadsheet at
 * 16px — a page with a visible cell grid, in Sheets green. Remix's
 * RiTableLine is a bare grid with no page around it, which at tab size looks
 * like a layout icon rather than a document.
 *
 * `currentColor` is deliberately NOT used: a table should stay recognisably
 * green whether or not its tab is selected, the same way a file type keeps
 * its colour in a file browser.
 */
export default function SheetIcon({ className = "size-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <path
        d="M3.5 1.75A.75.75 0 0 1 4.25 1h4.69c.2 0 .39.08.53.22l3.31 3.31c.14.14.22.33.22.53v9.19a.75.75 0 0 1-.75.75H4.25a.75.75 0 0 1-.75-.75V1.75Z"
        fill="#0F9D58"
      />
      <path d="M9 1.2v3.05c0 .28.22.5.5.5h3.05L9 1.2Z" fill="#0B7C46" />
      <path
        d="M5.5 6.75h5.5v5.5H5.5v-5.5Z"
        fill="#fff"
        fillOpacity="0.25"
      />
      <path
        d="M5.5 6.5h5.5M5.5 8.33h5.5M5.5 10.17h5.5M5.5 12h5.5M8.25 6.5v5.5"
        stroke="#fff"
        strokeWidth="0.9"
        strokeLinecap="round"
      />
    </svg>
  );
}
