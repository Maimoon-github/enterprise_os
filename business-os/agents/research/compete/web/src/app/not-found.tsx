import { ArrowLeft, LayoutDashboard } from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
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
        404 — Not found
      </p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
        This page went <span className="font-serif italic">off the radar.</span>
      </h1>
      <p className="mt-4 max-w-md text-muted-foreground">
        The page you&apos;re looking for doesn&apos;t exist or has moved. The rest of the site is
        still tracking just fine.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-secondary"
        >
          <ArrowLeft className="h-4 w-4" /> Back to home
        </Link>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 rounded-xl bg-foreground px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-foreground/90"
        >
          <LayoutDashboard className="h-4 w-4" /> Open dashboard
        </Link>
      </div>
    </div>
  );
}
