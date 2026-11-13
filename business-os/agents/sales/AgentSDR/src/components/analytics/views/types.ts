import type { AnalyticsResponseFor, AnalyticsView } from "@/lib/analytics/contract";

/** What every view component receives. `onSelectView` lets a view jump to another tab. */
export type ViewProps<V extends AnalyticsView> = {
  data: AnalyticsResponseFor<V>;
  /** A refetch is in flight; `data` is the previous render — dim, don't blank. */
  loading: boolean;
  onSelectView?: (view: AnalyticsView) => void;
};
