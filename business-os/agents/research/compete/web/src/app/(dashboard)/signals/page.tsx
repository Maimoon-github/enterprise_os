"use client";

import { Inbox, Signal as SignalIcon, X } from "lucide-react";
import { useState } from "react";

import { AsyncState } from "@/components/async-state";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { RunPipelineButton } from "@/components/run-pipeline-button";
import { SignalCard } from "@/components/signal-card";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompetitors, useSignals } from "@/lib/hooks";
import { SIGNAL_TYPES, type SignalQuery } from "@/lib/types";
import { signalMeta } from "@/lib/signal-meta";

export default function SignalsPage() {
  const competitors = useCompetitors();
  const [filters, setFilters] = useState<SignalQuery>({ limit: 200 });

  const signals = useSignals(filters);
  const nameById = new Map((competitors.data ?? []).map((c) => [c.id, c.name]));
  const rows = signals.data?.items ?? [];

  const hasFilters =
    !!filters.competitor ||
    !!filters.signal_type ||
    !!filters.min_significance ||
    !!filters.date_from;

  function set<K extends keyof SignalQuery>(key: K, value: SignalQuery[K]) {
    setFilters((f) => ({ ...f, [key]: value || undefined }));
  }

  return (
    <div>
      <PageHeader
        title="Signals"
        description="Every extracted signal, straight from the pipeline."
      />

      {/* Filters (same layout as Changes) */}
      <Card className="mb-5 p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Select
            aria-label="Competitor"
            value={filters.competitor ?? ""}
            onChange={(e) => set("competitor", e.target.value)}
          >
            <option value="">All competitors</option>
            {competitors.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Signal type"
            value={filters.signal_type ?? ""}
            onChange={(e) =>
              set("signal_type", (e.target.value || undefined) as SignalQuery["signal_type"])
            }
          >
            <option value="">All types</option>
            {SIGNAL_TYPES.map((t) => (
              <option key={t} value={t}>
                {signalMeta(t).label}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Minimum significance"
            value={filters.min_significance ?? ""}
            onChange={(e) =>
              set("min_significance", e.target.value ? Number(e.target.value) : undefined)
            }
          >
            <option value="">Any significance</option>
            {[2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                ≥ {n}
              </option>
            ))}
          </Select>
          <input
            type="date"
            aria-label="From date"
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={filters.date_from ?? ""}
            onChange={(e) => set("date_from", e.target.value || undefined)}
          />
        </div>
        {hasFilters && (
          <div className="mt-3 flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {rows.length} result{rows.length === 1 ? "" : "s"}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setFilters({ limit: 200 })}
              className="h-7 px-2 text-xs"
            >
              <X className="h-3 w-3" /> Clear filters
            </Button>
          </div>
        )}
      </Card>

      <AsyncState
        isLoading={signals.isLoading}
        isError={signals.isError}
        error={signals.error}
        onRetry={() => signals.refetch()}
        isEmpty={rows.length === 0}
        skeleton={
          <div className="flex flex-col gap-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        }
        empty={
          <EmptyState
            icon={hasFilters ? Inbox : SignalIcon}
            title={hasFilters ? "No matching signals" : "No signals yet"}
            description={
              hasFilters
                ? "Try widening or clearing your filters."
                : "Run the pipeline or seed demo data to populate the feed."
            }
            action={
              hasFilters ? (
                <Button variant="outline" size="sm" onClick={() => setFilters({ limit: 200 })}>
                  Clear filters
                </Button>
              ) : (
                <RunPipelineButton />
              )
            }
          />
        }
      >
        <div className="flex flex-col gap-3">
          {rows.map((s) => (
            <SignalCard key={s.signal_id} signal={s} competitorName={nameById.get(s.competitor_id)} />
          ))}
        </div>
      </AsyncState>
    </div>
  );
}
