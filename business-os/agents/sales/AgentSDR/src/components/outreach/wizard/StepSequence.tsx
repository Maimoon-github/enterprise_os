"use client";

import type { SequenceStep } from "@/lib/outreach/schema";
import SequenceComposer from "../SequenceComposer";

export default function StepSequence({
  campaignId,
  initialSequence,
  onBack,
  onContinue,
}: {
  campaignId: string;
  initialSequence: SequenceStep[];
  onBack: () => void;
  onContinue: (sequence: SequenceStep[]) => void;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-title-h5 text-text-strong-950">Build your sequence</h2>
        <p className="mt-1 text-paragraph-sm text-text-sub-600">
          Each step sends after the previous one, spaced by wait days.
        </p>
      </div>
      <SequenceComposer
        campaignId={campaignId}
        initialSequence={initialSequence}
        onBack={onBack}
        onSaved={onContinue}
        saveLabel="Save & continue"
      />
    </div>
  );
}
