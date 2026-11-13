"use client";

// Route-level error boundary: catches render/runtime errors anywhere below the
// root layout and keeps the user inside the site with a retry path.

import { Home, RotateCcw } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface the real error in the console for debugging.
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-6 text-center text-foreground">
      <Link href="/" aria-label="compete home">
        <Image
          src="/compete-logo.svg"
          alt="compete logo"
          width={48}
          height={48}
          priority
          className="h-12 w-12 rounded-xl"
        />
      </Link>

      <p className="mt-8 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
        Something broke
      </p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
        That wasn&apos;t <span className="font-serif italic">supposed to happen.</span>
      </h1>
      <p className="mt-4 max-w-md text-muted-foreground">
        An unexpected error interrupted this page. Retrying usually fixes it; if it keeps
        happening, the console has the details.
      </p>
      {error.digest && (
        <p className="mt-2 font-mono text-xs text-muted-foreground/60">ref {error.digest}</p>
      )}

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-secondary"
        >
          <Home className="h-4 w-4" /> Back to home
        </Link>
        <button
          type="button"
          onClick={reset}
          className="inline-flex items-center gap-1.5 rounded-xl bg-foreground px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-foreground/90"
        >
          <RotateCcw className="h-4 w-4" /> Try again
        </button>
      </div>
    </div>
  );
}
