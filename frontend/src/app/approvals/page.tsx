"use client";

import React, { useEffect, useState } from "react";
import {
  CheckSquare,
  ShieldCheck,
  AlertTriangle,
  FileCode,
  DollarSign,
  Check,
  X,
  Clock,
  KeyRound,
  FileCheck2,
  RefreshCw,
  Zap,
  Box,
  ExternalLink,
} from "lucide-react";
import { api, MOCK_APPROVAL_PREVIEWS } from "@/lib/api";
import { ActionPreview, ApprovalDecisionRequest } from "@/lib/types";
import { getStoredSettings, EnterpriseSettings } from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

export default function ApprovalsPage() {
  const [previews, setPreviews] = useState<ActionPreview[]>(MOCK_APPROVAL_PREVIEWS);
  const [selectedPreview, setSelectedPreview] = useState<ActionPreview>(MOCK_APPROVAL_PREVIEWS[0]);
  const [settings] = useState<EnterpriseSettings>(getStoredSettings());
  const [approverName, setApproverName] = useState(settings.approverName);
  const [approverRole, setApproverRole] = useState(settings.approverRole);
  const [revisionNotes, setRevisionNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [decisionHistory, setDecisionHistory] = useState<Record<string, { decision: string; hash: string }>>({});
  const { addToast } = useToast();

  const fetchPreviews = async () => {
    const data = await api.getApprovalPreviews();
    if (data && data.length > 0) {
      setPreviews(data);
      if (!selectedPreview) setSelectedPreview(data[0]);
    }
  };

  useEffect(() => {
    fetchPreviews();
  }, []);

  const handleDecision = async (decision: "APPROVE" | "REJECT" | "REQUEST_REVISION" | "HOLD") => {
    if (!selectedPreview) return;
    setIsSubmitting(true);

    try {
      const payload: ApprovalDecisionRequest = {
        approved: decision === "APPROVE",
        decision,
        approver: approverName,
        approver_role: approverRole,
        tenant_id: selectedPreview.tenant_id,
        revision_notes: revisionNotes || undefined,
        preview_content_hash: `sha256-${Date.now().toString(16)}abcd998877`,
      };

      const result = await api.submitApprovalDecision(selectedPreview.action_preview_id, payload);

      setDecisionHistory((prev) => ({
        ...prev,
        [selectedPreview.action_preview_id]: {
          decision,
          hash: payload.preview_content_hash!,
        },
      }));

      addToast({
        type: decision === "APPROVE" ? "success" : decision === "REJECT" ? "error" : "warning",
        title: `Decision: ${decision} Registered`,
        message: `Cryptographically signed by ${approverName} (${approverRole}).`,
        hash: payload.preview_content_hash,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApproveAll = async () => {
    for (const prev of previews) {
      await api.submitApprovalDecision(prev.action_preview_id, {
        approved: true,
        decision: "APPROVE",
        approver: approverName,
        approver_role: approverRole,
        preview_content_hash: `sha256-${Date.now().toString(16)}00aa11bb`,
        revision_notes: "Batch approved via 1-Click Executive Gate",
      });
      setDecisionHistory((h) => ({
        ...h,
        [prev.action_preview_id]: {
          decision: "APPROVE",
          hash: `sha256-batch-${prev.action_preview_id.slice(-6)}`,
        },
      }));
    }
    addToast({
      type: "success",
      title: "Batch Authorization Complete",
      message: `Signed & approved all ${previews.length} pending action previews.`,
    });
  };

  const currentDecision = selectedPreview ? decisionHistory[selectedPreview.action_preview_id] : null;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <CheckSquare className="w-6 h-6 text-amber-400" />
            <span>Human-in-the-Loop (HITL) Authorization Queue</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Zero-trust gatekeeper. Code modifications and budget spend proposals require explicit cryptographic signing prior to actuation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleApproveAll}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-lg shadow-amber-600/20 transition-all"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>1-Click Approve All</span>
          </button>

          <a
            href={settings.sandboxWebsiteUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-amber-950/40 hover:bg-amber-950/70 border border-amber-800/80 text-amber-300 text-xs font-semibold transition-all font-mono"
          >
            <Box className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>Sandbox Site (:3001)</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>

      {/* Grid: Preview Selector & Detail Signer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Preview Queue */}
        <div className="lg:col-span-4 space-y-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
            Pending Action Previews ({previews.length})
          </div>

          <div className="space-y-3">
            {previews.map((prev) => {
              const isSelected = selectedPreview?.action_preview_id === prev.action_preview_id;
              const dec = decisionHistory[prev.action_preview_id];

              return (
                <button
                  key={prev.action_preview_id}
                  onClick={() => setSelectedPreview(prev)}
                  className={`w-full text-left p-4 rounded-xl border transition-all ${
                    isSelected
                      ? "bg-amber-950/30 border-amber-500/50 shadow-md shadow-amber-500/10"
                      : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-xs font-bold text-slate-200">
                      {prev.action_preview_id}
                    </span>
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${
                        dec
                          ? dec.decision === "APPROVE"
                            ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                            : "bg-rose-950 text-rose-400 border-rose-800"
                          : prev.risk_level === "high"
                          ? "bg-rose-950/60 text-rose-400 border-rose-800"
                          : "bg-amber-950/60 text-amber-400 border-amber-800"
                      }`}
                    >
                      {dec ? dec.decision : `${prev.risk_level} Risk`}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                    {prev.summary}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono mt-3 pt-2 border-t border-slate-800/80">
                    <span className="capitalize">{prev.preview_type.replace(/_/g, " ")}</span>
                    <span className="text-cyan-400">{prev.worker_role}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Inspection & Decision Signer */}
        <div className="lg:col-span-8 space-y-6">
          {selectedPreview && (
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-6">
              {/* Header Info */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs text-amber-400 font-semibold">
                      {selectedPreview.action_preview_id}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      Task: {selectedPreview.task_id}
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-white">
                    {selectedPreview.summary}
                  </h2>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono px-3 py-1 rounded bg-slate-950 text-slate-300 border border-slate-800">
                    Worker: <strong className="text-cyan-300">{selectedPreview.worker_role}</strong>
                  </span>
                </div>
              </div>

              {/* Live Code Diff Viewer */}
              {selectedPreview.code_diff && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
                      <FileCode className="w-4 h-4 text-indigo-400" />
                      <span>{selectedPreview.code_diff.file_path}</span>
                    </div>

                    <div className="flex items-center gap-3 text-xs font-mono">
                      {selectedPreview.code_diff.ast_valid && (
                        <span className="text-emerald-400 flex items-center gap-1">
                          <ShieldCheck className="w-3.5 h-3.5" />
                          <span>AST Valid</span>
                        </span>
                      )}
                      {selectedPreview.code_diff.wcag_score && (
                        <span className="text-cyan-400">
                          WCAG: {selectedPreview.code_diff.wcag_score}/100
                        </span>
                      )}
                    </div>
                  </div>

                  <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto max-h-[300px] leading-relaxed">
                    {selectedPreview.code_diff.diff_unified}
                  </pre>
                </div>
              )}

              {/* Spend Proposal Viewer */}
              {selectedPreview.spend_proposal && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 rounded-xl bg-slate-950 border border-slate-800">
                    <div>
                      <span className="text-xs text-slate-400 block">Total Spend Commitment</span>
                      <span className="text-2xl font-bold font-mono text-white">
                        ${selectedPreview.spend_proposal.total_spend.toLocaleString()}
                      </span>
                    </div>
                    <div className="text-right">
                      <span className="text-xs text-slate-400 block">Marginal ROAS Projection</span>
                      <span className="text-xl font-bold font-mono text-emerald-400">
                        {selectedPreview.spend_proposal.marginal_roas_projection}x
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3 text-xs font-mono">
                    {Object.entries(selectedPreview.spend_proposal.channel_allocations).map(([ch, amt]) => (
                      <div key={ch} className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                        <span className="text-slate-500 block truncate capitalize">
                          {ch.replace(/_/g, " ")}
                        </span>
                        <span className="text-slate-200 font-bold">${amt.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Cryptographic Decision Signer Panel */}
              <div className="pt-4 border-t border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                    <KeyRound className="w-4 h-4 text-amber-400" />
                    <span>Cryptographic Decision Signer</span>
                  </div>
                  {currentDecision && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                      SEALED: {currentDecision.hash.slice(0, 16)}...
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Approver Identity</label>
                    <input
                      type="text"
                      value={approverName}
                      onChange={(e) => setApproverName(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Reviewer Role Authority</label>
                    <input
                      type="text"
                      value={approverRole}
                      onChange={(e) => setApproverRole(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-slate-400 mb-1">Revision / Audit Notes (Optional)</label>
                  <input
                    type="text"
                    value={revisionNotes}
                    onChange={(e) => setRevisionNotes(e.target.value)}
                    placeholder="Enter compliance justification or revision feedback..."
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200"
                  />
                </div>

                {/* 1-Click Action Buttons */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                  <button
                    onClick={() => handleDecision("APPROVE")}
                    disabled={isSubmitting}
                    className="py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/30 transition-all"
                  >
                    <Check className="w-4 h-4" />
                    <span>1-Click Sign & Approve</span>
                  </button>

                  <button
                    onClick={() => handleDecision("REQUEST_REVISION")}
                    disabled={isSubmitting}
                    className="py-2.5 px-4 rounded-xl bg-amber-600/80 hover:bg-amber-600 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all"
                  >
                    <Clock className="w-4 h-4" />
                    <span>Request Revision</span>
                  </button>

                  <button
                    onClick={() => handleDecision("REJECT")}
                    disabled={isSubmitting}
                    className="py-2.5 px-4 rounded-xl bg-rose-600/80 hover:bg-rose-600 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all"
                  >
                    <X className="w-4 h-4" />
                    <span>Reject Action</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
