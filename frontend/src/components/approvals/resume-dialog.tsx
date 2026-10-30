"use client";

import { useState } from "react";

interface ResumeDialogProps {
  isOpen: boolean;
  approvalId?: string;
  isApprovalAction?: boolean;
  onClose: () => void;
  onResume: (notes: string, approved: boolean) => void;
}

export function ResumeDialog({
  isOpen,
  approvalId,
  isApprovalAction = true,
  onClose,
  onResume,
}: ResumeDialogProps) {
  const [notes, setNotes] = useState("");

  if (!isOpen) return null;

  const handleSubmit = () => {
    onResume(notes, isApprovalAction);
    setNotes("");
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-bloodstone-canvas/80 backdrop-blur-md flex items-center justify-center p-4 z-50">
      <div className="glass-panel-elevated rounded-xl p-6 max-w-lg w-full space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-bloodstone-text">
            {isApprovalAction ? "Confirm Approval & Trigger Fan-Out" : "Request Creative Revision"}
          </h3>
          <span className="text-xs text-bloodstone-text-muted font-mono">
            {approvalId ? `Approval: ${approvalId.slice(0, 8)}...` : ""}
          </span>
        </div>

        <p className="text-xs text-bloodstone-text-muted leading-normal">
          {isApprovalAction
            ? "Approving will resume the interrupted LangGraph node, trigger idempotent post-approval platform publishing fan-out across all 8 channels, and record audit lineage."
            : "Requesting revision increments the Reflexion counter (max 2 revisions) and feeds your critique back into the Campaign Creative sub-graph."}
        </p>

        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={
            isApprovalAction
              ? "Optional approval context or sign-off notes..."
              : "Specify required adjustments (e.g., tone refinement, hook adjustment, CTA modification)..."
          }
          rows={4}
          className="w-full glass-input p-3 text-xs text-bloodstone-text placeholder:text-bloodstone-text-dim"
        />

        <div className="flex justify-end gap-2.5 pt-2">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 text-xs text-bloodstone-text-muted hover:text-bloodstone-text hover:bg-glass-base rounded-lg transition duration-fast ease-out-expo"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all duration-normal ease-out-expo ${
              isApprovalAction ? "glass-emerald text-bloodstone-text" : "glass-crimson text-bloodstone-text"
            }`}
          >
            {isApprovalAction ? "Submit Approval & Resume" : "Submit Critique & Loop"}
          </button>
        </div>
      </div>
    </div>
  );
}
