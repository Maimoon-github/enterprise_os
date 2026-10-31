"use client";

import { StatusBadge } from "@/components/common/status-badge";

interface PlatformAsset {
  platform: string;
  copy_text?: string;
  copy?: string;
  aspect_ratio?: string;
  scheduled_utc?: string;
  idempotency_key?: string;
  compliance_passed?: boolean;
}

interface BlueprintViewerProps {
  blueprint: {
    campaign_id?: string;
    objective?: string;
    target_audience_segments?: string[];
    positioning_statement?: string;
    platform_assets?: PlatformAsset[];
    [key: string]: any;
  } | null;
}

export function BlueprintViewer({ blueprint }: BlueprintViewerProps) {
  if (!blueprint) {
    return (
      <div className="p-4 glass-panel rounded-lg text-xs text-bloodstone-text-muted">
        No campaign blueprint loaded.
      </div>
    );
  }

  const assets = blueprint.platform_assets || [];

  return (
    <div className="space-y-4 text-xs font-mono">
      <div className="glass-panel p-4 rounded-lg space-y-2 font-sans">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-bloodstone-text text-sm">
            {blueprint.objective || "Campaign Blueprint"}
          </span>
          <span className="text-[11px] px-2 py-0.5 rounded bg-glass-base text-bloodstone-mint border border-glass-subtle font-mono">
            ID: {blueprint.campaign_id || "cmp_default"}
          </span>
        </div>
        {blueprint.positioning_statement && (
          <p className="text-xs text-bloodstone-text-muted">
            {blueprint.positioning_statement}
          </p>
        )}
      </div>

      {assets.length > 0 && (
        <div className="space-y-3 font-sans">
          <div className="text-xs font-semibold uppercase tracking-wider text-bloodstone-mint">
            Platform Asset Specifications ({assets.length})
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {assets.map((asset, idx) => {
              const text = asset.copy_text || asset.copy || "";
              return (
                <div key={idx} className="p-3.5 glass-panel rounded-lg space-y-2 border border-glass-subtle">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs uppercase tracking-wide text-bloodstone-text">
                      {asset.platform}
                    </span>
                    <StatusBadge
                      status={asset.compliance_passed ? "compliant" : "pending"}
                    />
                  </div>
                  <p className="text-xs text-bloodstone-text-muted whitespace-pre-wrap line-clamp-3">
                    {text}
                  </p>
                  <div className="flex items-center justify-between text-[11px] text-bloodstone-text-dim font-mono pt-1 border-t border-glass-dark">
                    <span>Ratio: {asset.aspect_ratio || "1:1"}</span>
                    <span>Chars: {text.length}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <details className="glass-panel p-3 rounded-lg text-[11px]">
        <summary className="cursor-pointer font-sans text-xs text-bloodstone-text-muted hover:text-bloodstone-text">
          View Raw campaign.json Blueprint
        </summary>
        <pre className="mt-3 p-3 bg-bloodstone-canvas/60 rounded text-bloodstone-text overflow-x-auto scrollbar-thin">
          {JSON.stringify(blueprint, null, 2)}
        </pre>
      </details>
    </div>
  );
}
