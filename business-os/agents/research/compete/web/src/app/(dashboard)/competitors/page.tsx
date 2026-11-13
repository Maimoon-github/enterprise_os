"use client";

import { Building2, Globe, TrendingUp } from "lucide-react";
import Link from "next/link";

import { AsyncState } from "@/components/async-state";
import { CompetitorAvatar } from "@/components/competitor-avatar";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { RelativeTime } from "@/components/relative-time";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompetitors } from "@/lib/hooks";

const TIER_LABEL: Record<number, string> = { 1: "Tier 1", 2: "Tier 2", 3: "Tier 3" };

export default function CompetitorsPage() {
  const competitors = useCompetitors();
  const rows = competitors.data ?? [];

  return (
    <div>
      <PageHeader
        title="Competitors"
        description="Everyone you track, with their signal activity at a glance."
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link href="/settings">Manage in Settings</Link>
          </Button>
        }
      />

      <AsyncState
        isLoading={competitors.isLoading}
        isError={competitors.isError}
        error={competitors.error}
        onRetry={() => competitors.refetch()}
        isEmpty={rows.length === 0}
        skeleton={
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-40 w-full" />
            ))}
          </div>
        }
        empty={
          <EmptyState
            icon={Building2}
            title="No competitors tracked"
            description="Add your first competitor in Settings to start collecting signals."
            action={
              <Button variant="outline" size="sm" asChild>
                <Link href="/settings">Go to Settings</Link>
              </Button>
            }
          />
        }
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((c) => (
            <Link
              key={c.id}
              href={`/competitors/${c.id}`}
              className="group rounded-lg border bg-card p-5 transition-colors hover:border-primary/40 hover:bg-secondary/40"
            >
              <div className="flex items-center gap-3">
                <CompetitorAvatar name={c.name} id={c.id} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium group-hover:underline">{c.name}</p>
                  <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
                    {c.domain && <Globe className="h-3 w-3 shrink-0" />}
                    {c.domain ?? c.industry ?? "—"}
                  </p>
                </div>
                <Badge variant="outline">{TIER_LABEL[c.tier] ?? `Tier ${c.tier}`}</Badge>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-md bg-secondary/50 px-2 py-2">
                  <p className="tabular text-lg font-semibold">{c.signal_count}</p>
                  <p className="text-[11px] text-muted-foreground">Signals</p>
                </div>
                <div className="rounded-md bg-secondary/50 px-2 py-2">
                  <p className="tabular flex items-center justify-center gap-1 text-lg font-semibold">
                    {c.high_significance_count > 0 && (
                      <TrendingUp className="h-3.5 w-3.5 text-primary" />
                    )}
                    {c.high_significance_count}
                  </p>
                  <p className="text-[11px] text-muted-foreground">High sig.</p>
                </div>
                <div className="rounded-md bg-secondary/50 px-2 py-2">
                  <p className="tabular text-lg font-semibold">{c.tracked_url_count}</p>
                  <p className="text-[11px] text-muted-foreground">URLs</p>
                </div>
              </div>

              <p className="mt-3 text-xs text-muted-foreground">
                {c.last_signal_at ? (
                  <>
                    Last signal <RelativeTime value={c.last_signal_at} />
                  </>
                ) : (
                  "No signals yet"
                )}
              </p>
            </Link>
          ))}
        </div>
      </AsyncState>
    </div>
  );
}
