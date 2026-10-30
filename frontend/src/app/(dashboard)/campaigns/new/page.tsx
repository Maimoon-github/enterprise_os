"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CampaignForm } from "@/components/campaigns/campaign-form";
import { campaignsApi } from "@/lib/api/endpoints/campaigns";
import { CampaignCreate } from "@marketing-os/contracts";

export default function NewCampaignPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleCreateCampaign = async (payload: CampaignCreate) => {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const created = await campaignsApi.create(payload);
      if (created?.id) {
        router.push(`/campaigns/${created.id}`);
      } else {
        router.push("/campaigns");
      }
    } catch (err: any) {
      console.error("Failed to create campaign:", err);
      setErrorMessage(err?.message || "Failed to initialize campaign execution. Check API connection.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Synthesize New Campaign Blueprint</h1>
        <p className="text-slate-400 text-sm">
          Define strategic directives and platform targets. The LangGraph supervisor will coordinate research and creative subgraphs.
        </p>
      </div>

      {errorMessage && (
        <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-rose-300 text-xs">
          {errorMessage}
        </div>
      )}

      <CampaignForm onSubmit={handleCreateCampaign} isLoading={isSubmitting} />
    </div>
  );
}
