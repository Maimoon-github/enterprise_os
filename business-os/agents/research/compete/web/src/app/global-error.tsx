"use client";

// Last-resort boundary: replaces the root layout when it crashes, so nothing
// from globals.css or the layout (fonts, providers) is available here. Styles
// are inline and mirror the brand palette (paper, ink, lime).

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          padding: "0 24px",
          background: "#faf9f5",
          color: "#1a1a14",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            background: "#BAEB33",
            display: "grid",
            placeItems: "center",
            fontWeight: 700,
            fontSize: 22,
          }}
        >
          c
        </div>
        <p
          style={{
            marginTop: 32,
            fontSize: 12,
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            color: "#6b6a60",
          }}
        >
          Something broke
        </p>
        <h1 style={{ marginTop: 12, fontSize: 36, fontWeight: 600, letterSpacing: "-0.02em" }}>
          The whole page crashed.
        </h1>
        <p style={{ marginTop: 16, maxWidth: 420, color: "#6b6a60", lineHeight: 1.6 }}>
          An unexpected error took down the app shell. Reloading usually fixes it.
        </p>
        {error.digest && (
          <p style={{ marginTop: 8, fontFamily: "monospace", fontSize: 12, color: "#9b9a90" }}>
            ref {error.digest}
          </p>
        )}
        <button
          type="button"
          onClick={reset}
          style={{
            marginTop: 32,
            padding: "10px 20px",
            borderRadius: 12,
            border: "none",
            background: "#1a1a14",
            color: "#faf9f5",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Reload the app
        </button>
      </body>
    </html>
  );
}
