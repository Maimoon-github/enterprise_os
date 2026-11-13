import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { LandingFooter } from "@/components/landing/landing-footer";
import { LandingNav } from "@/components/landing/landing-nav";

export const metadata: Metadata = {
  title: "Why this project has a frontend · compete",
  description:
    "Most data engineering projects stop at the pipeline. compete didn't. Why it has a real product surface, why the deployed site runs with no backend, and what you need to run it yourself.",
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="scroll-mt-28 border-t border-border py-10 first:border-t-0 first:pt-0">
      <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
      <div className="mt-5 space-y-4 text-[0.95rem] leading-relaxed text-foreground/85">
        {children}
      </div>
    </section>
  );
}

function Code({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-xl border border-border bg-[hsl(var(--ink))] p-4 text-[0.82rem] leading-relaxed text-[hsl(var(--bone))] scrollbar-thin">
      <code>{children}</code>
    </pre>
  );
}

function K({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[0.85em] text-foreground">
      {children}
    </code>
  );
}

export default function NotesPage() {
  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <LandingNav />

      <main className="mx-auto max-w-[760px] px-4 pb-20 pt-28 sm:px-6 sm:pt-32">
        {/* Header */}
        <header>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Field notes
          </p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
            Why this project has a frontend
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-muted-foreground">
            Most data engineering projects stop at the pipeline. This one didn&apos;t, and here
            is the reasoning behind it, including why the site you&apos;re reading runs with no
            backend at all.
          </p>
        </header>

        <article className="mt-12">
          <Section title="Data projects are usually invisible">
            <p>
              A typical data engineering portfolio is a README, an architecture diagram, and maybe
              a notebook with a few charts. The pipeline underneath might be genuinely good, tested,
              idempotent, careful about cost, and none of that comes across, because there is
              nothing to look at. You read the code or you take the author&apos;s word for it. I have
              clicked through a lot of these projects and remembered almost none of them.
            </p>
            <p>
              That is the gap I wanted to close. compete ingests competitor web pages, runs the
              changed ones through an LLM, scores what it finds, and files the results into a
              warehouse. That is real work. If the only way to see it is to clone the repo and run
              the pipeline locally, then almost nobody ever will.
            </p>
          </Section>

          <Section title="So the frontend is the point">
            <p>
              I gave compete a proper product surface: an overview, a page per competitor, a
              filterable feed of detected changes, and weekly reports you can download as PDF. It
              shares one design system with the marketing site and this page, warm paper and ink
              surfaces, a single lime accent, one sans typeface and one serif for editorial moments.
              Every data view has explicit loading, empty, and error states, which is most of what
              makes a dashboard feel finished instead of half-built.
            </p>
            <p>
              The design exists to make the engineering legible. Good pipeline work deserves
              somewhere to show up, and a dry repo isn&apos;t it.
            </p>
          </Section>

          <Section title="Kept technical on purpose">
            <p>
              A polished shell over nothing is easy to spot and worth nothing, so I wanted a reader
              to be able to confirm the system actually runs. The dashboard reads real dbt marts
              through a FastAPI service. The whole pipeline runs end to end from one CLI. The numbers
              on screen come from an actual DuckDB file, not a JSON someone hand-wrote to look
              plausible.
            </p>
            <p>
              The <Link href="/docs" className="font-medium text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground">docs page</Link>{" "}
              walks through every stage, collection, extraction, the change-detection gate, the
              warehouse, the API, and it is honest about where the system falls short. If you want to
              check my work, the seams are all exposed on purpose.
            </p>
          </Section>

          <Section title="Why the deployed site is static">
            <p>
              Here is the part that surprises people. The version of compete you are looking at has
              no backend. There is no FastAPI server running, no database, nothing to wake up.
            </p>
            <p>
              Before each deploy, <K>scripts/export_static_data.py</K> queries the warehouse once and
              writes the results to plain JSON under <K>/api-static</K>: competitors, signals,
              changes, per-competitor pricing and hiring, the reports. The frontend detects static
              mode and reads those files directly instead of calling an API. Create, edit, and delete
              still work; they are applied to a <K>localStorage</K> overlay in your browser, so the
              settings screen stays interactive with nothing on the other end to write to.
            </p>
            <p>
              Two reasons this is the right call for a portfolio piece. It costs nothing to host,
              static files on a CDN, no server bill, no database to keep alive. And it never
              embarrasses me with a cold-start API returning an empty dashboard to the one person who
              opens the link on a Sunday. The tradeoff is that the data is a snapshot. A weekly GitHub
              Actions run regenerates the JSON and commits it, so the site stays current without ever
              running a server in production.
            </p>
          </Section>

          <Section title="What you need to run it yourself">
            <p>
              If you just want to look, the deployed site is the whole thing. Open the dashboard from
              the nav and click around.
            </p>
            <p>
              If you want live data flowing through the real pipeline, it is a short setup from a
              clean clone:
            </p>
            <Code>{`uv sync --extra dev --extra dbt --extra api   # Python env + deps
uv run compete init-db                        # create the DuckDB schema
uv run python scripts/seed_demo.py --build    # demo data + dbt build
uv run compete-api                            # FastAPI on :8000`}</Code>
            <p>
              Then start the dashboard against the live API with{" "}
              <K>NEXT_PUBLIC_STATIC_DATA=0 npm run dev</K> inside <K>web/</K>. Left unset, dev reads
              the same static snapshot as production, which is the faster way to just click around.
            </p>
            <p>
              One honest caveat: the seeded dataset is curated. The collectors are real and run
              against live sites, but the demo data is planted so that every feature has something to
              show without waiting a month for real history to accumulate. Everything you click is
              wired to the actual system. The contents are just primed. If something looks broken, it
              is a bug rather than a mockup, because the wiring underneath is all real.
            </p>
          </Section>
        </article>
      </main>

      <LandingFooter />
    </div>
  );
}
