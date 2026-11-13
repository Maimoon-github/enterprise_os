"use client";

import SequenceComposer from "./SequenceComposer";
import type { SequenceStep } from "@/lib/outreach/schema";

export default function SequenceTab({
  campaignId,
  initialSequence,
  onSaved,
}: {
  campaignId: string;
  initialSequence: SequenceStep[];
  onSaved?: (sequence: SequenceStep[]) => void;
}) {
  return <SequenceComposer campaignId={campaignId} initialSequence={initialSequence} onSaved={onSaved} />;
}
