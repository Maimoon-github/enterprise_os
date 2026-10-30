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
    <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-5">
      <div>
        <label className="block text-xs uppercase font-semibold text-slate-400 mb-1.5">
          Brand Workspace
        </label>
        <select
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
        >
          {brands.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name} ({b.slug})
            </option>
          ))}
        </select>
        {validationErrors.brandId && (
          <p className="text-xs text-rose-400 mt-1">{validationErrors.brandId}</p>
        )}
      </div>

      <div>
        <label className="block text-xs uppercase font-semibold text-slate-400 mb-1.5">
          Campaign Title
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Q4 Multi-Platform Platform Launch"
          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
        />
        {validationErrors.name && (
          <p className="text-xs text-rose-400 mt-1">{validationErrors.name}</p>
        )}
      </div>

      <div>
        <label className="block text-xs uppercase font-semibold text-slate-400 mb-1.5">
          Strategic Objective & Directives
        </label>
        <textarea
          rows={4}
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          placeholder="Describe positioning, target audience segments, key messaging, and conversion goals..."
          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
        />
        {validationErrors.objective && (
          <p className="text-xs text-rose-400 mt-1">{validationErrors.objective}</p>
        )}
      </div>

      <div>
        <label className="block text-xs uppercase font-semibold text-slate-400 mb-2">
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
                className={`px-3 py-2 rounded-lg border text-xs font-medium text-left transition flex items-center justify-between ${
                  isSelected
                    ? "bg-indigo-950/60 border-indigo-500 text-white"
                    : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                <span>{p.label}</span>
                <span className={`text-[10px] ${isSelected ? "text-indigo-400 font-bold" : "text-slate-600"}`}>
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
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition"
        >
          {isLoading ? "Synthesizing Blueprint..." : "Synthesize Campaign Blueprint"}
        </button>
      </div>
    </form>
  );
}
