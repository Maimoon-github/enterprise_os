"use client";

import { useEffect, useState } from "react";
import { CampaignCreate, PlatformType } from "@marketing-os/contracts";
import { apiClient } from "@/lib/api/client";

const ALL_PLATFORMS: { id: PlatformType; label: string }[] = [
  { id: "linkedin", label: "LinkedIn" },
  { id: "x", label: "X (Twitter)" },
  { id: "youtube", label: "YouTube" },
  { id: "instagram", label: "Instagram" },
  { id: "threads", label: "Threads" },
  { id: "facebook", label: "Facebook" },
  { id: "pinterest", label: "Pinterest" },
  { id: "google_business_profile", label: "Google Business" },
];

interface BrandOption {
  id: string;
  name: string;
  slug: string;
}

interface CampaignFormProps {
  onSubmit: (payload: CampaignCreate) => Promise<void> | void;
  isLoading?: boolean;
}

export function CampaignForm({ onSubmit, isLoading = false }: CampaignFormProps) {
  const [name, setName] = useState("");
  const [objective, setObjective] = useState("");
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<BrandOption[]>([]);
  const [selectedPlatforms, setSelectedPlatforms] = useState<PlatformType[]>([
    "linkedin",
    "x",
    "instagram",
    "threads",
  ]);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    apiClient<BrandOption[]>("/brands")
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setBrands(data);
          setBrandId(data[0].id);
        } else {
          // Fallback demo brand uuid
          const defaultUuid = "00000000-0000-0000-0000-000000000001";
          setBrands([{ id: defaultUuid, name: "Apex Horizon (Default)", slug: "apex-horizon" }]);
          setBrandId(defaultUuid);
        }
      })
      .catch(() => {
        const defaultUuid = "00000000-0000-0000-0000-000000000001";
        setBrands([{ id: defaultUuid, name: "Apex Horizon (Default)", slug: "apex-horizon" }]);
        setBrandId(defaultUuid);
      });
  }, []);

  const togglePlatform = (platform: PlatformType) => {
    setSelectedPlatforms((prev) =>
      prev.includes(platform) ? prev.filter((p) => p !== platform) : [...prev, platform]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const errors: Record<string, string> = {};

    if (!name.trim()) {
      errors.name = "Campaign title is required.";
    } else if (name.length > 255) {
      errors.name = "Campaign title cannot exceed 255 characters.";
    }

    if (!objective.trim()) {
      errors.objective = "Strategic objective is required.";
    }

    if (!brandId) {
      errors.brandId = "Target brand must be selected.";
    }

    if (selectedPlatforms.length === 0) {
      errors.platforms = "At least one target platform must be selected.";
    }

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    setValidationErrors({});
    onSubmit({
      brand_id: brandId,
      name: name.trim(),
      objective: objective.trim(),
      target_platforms: selectedPlatforms,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="glass-card p-6 space-y-5">
      <div>
        <label className="block text-xs uppercase font-semibold text-bloodstone-text-muted mb-1.5">
          Brand Workspace
        </label>
        <select
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
          className="w-full glass-input px-3 py-2 text-sm text-bloodstone-text"
        >
          {brands.map((b) => (
            <option key={b.id} value={b.id} className="bg-bloodstone-canvas text-bloodstone-text">
              {b.name} ({b.slug})
            </option>
          ))}
        </select>
        {validationErrors.brandId && (
          <p className="text-xs text-rose-400 mt-1">{validationErrors.brandId}</p>
        )}
      </div>

      <div>
        <label className="block text-xs uppercase font-semibold text-bloodstone-text-muted mb-1.5">
          Campaign Title
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Q4 Multi-Platform Platform Launch"
          className="w-full glass-input px-3 py-2 text-sm text-bloodstone-text placeholder:text-bloodstone-text-dim"
        />
        {validationErrors.name && (
          <p className="text-xs text-rose-400 mt-1">{validationErrors.name}</p>
        )}
      </div>

      <div>
        <label className="block text-xs uppercase font-semibold text-bloodstone-text-muted mb-1.5">
          Strategic Objective & Directives
        </label>
        <textarea
          rows={4}
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          placeholder="Describe positioning, target audience segments, key messaging, and conversion goals..."
          className="w-full glass-input px-3 py-2 text-sm text-bloodstone-text placeholder:text-bloodstone-text-dim"
        />
        {validationErrors.objective && (
          <p className="text-xs text-rose-400 mt-1">{validationErrors.objective}</p>
        )}
      </div>

      <div>
        <label className="block text-xs uppercase font-semibold text-bloodstone-text-muted mb-2">
          Target Platform Matrix ({selectedPlatforms.length} selected)
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {ALL_PLATFORMS.map((p) => {
            const isSelected = selectedPlatforms.includes(p.id);
            return (
              <button
                type="button"
                key={p.id}
                onClick={() => togglePlatform(p.id)}
                className={`px-3 py-2 rounded-lg border text-xs font-medium text-left transition-all duration-fast flex items-center justify-between ${
                  isSelected
                    ? "bg-glass-emerald border-glass-specular text-bloodstone-mint shadow-bloodstone-glow"
                    : "bg-glass-base border-glass-subtle text-bloodstone-text-muted hover:text-bloodstone-text"
                }`}
              >
                <span>{p.label}</span>
                <span className={`text-[10px] ${isSelected ? "text-bloodstone-mint font-bold" : "text-bloodstone-text-dim"}`}>
                  {isSelected ? "✓" : "+"}
                </span>
              </button>
            );
          })}
        </div>
        {validationErrors.platforms && (
          <p className="text-xs text-rose-400 mt-1">{validationErrors.platforms}</p>
        )}
      </div>

      <div className="pt-2">
        <button
          type="submit"
          disabled={isLoading}
          className="glass-emerald text-bloodstone-text disabled:opacity-50 px-5 py-2.5 rounded-lg text-sm font-medium transition duration-normal ease-out-expo"
        >
          {isLoading ? "Synthesizing Blueprint..." : "Synthesize Campaign Blueprint"}
        </button>
      </div>
    </form>
  );
}
