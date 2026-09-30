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
} from "lucide-react";
import { api, MOCK_APPROVAL_PREVIEWS } from "@/lib/api";
import { ActionPreview, ApprovalDecisionRequest } from "@/lib/types";

export default function ApprovalsPage() {
  const [previews, setPreviews] = useState<ActionPreview[]>(MOCK_APPROVAL_PREVIEWS);
  const [selectedPreview, setSelectedPreview] = useState<ActionPreview>(MOCK_APPROVAL_PREVIEWS[0]);
  const [approverName, setApproverName] = useState("SecOps Lead (Maimoon)");
  const [approverRole, setApproverRole] = useState("Security Officer");
  const [revisionNotes, setRevisionNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [decisionHistory, setDecisionHistory] = useState<Record<string, { decision: string; hash: string }>>({});

  useEffect(() => {
    const fetchPreviews = async () => {
      const data = await api.getApprovalPreviews();
      if (data && data.length > 0) {
        setPreviews(data);
        if (!selectedPreview) setSelectedPreview(data[0]);
      }
    };
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
          hash: result.signature_verified ? payload.preview_content_hash! : "unverified",
        },
      }));
    } finally {
      setIsSubmitting(false);
    }
  };

  const currentDecision = selectedPreview ? decisionHistory[selectedPreview.action_preview_id] : null;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
          <CheckSquare className="w-6 h-6 text-amber-400" />
          <span>Human-in-the-Loop (HITL) Authorization Queue</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Zero-trust gatekeeper. Code modifications and budget spend proposals require explicit cryptographic signing prior to execution.
        </p>
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
                  <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-950 text-slate-300 border border-slate-800">
                    Tenant: {selectedPreview.tenant_id}
                  </span>
                </div>
              </div>

              {/* Inspection Payload */}
              {selectedPreview.preview_type === "live_code_diff" && selectedPreview.code_diff && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-mono text-indigo-400 flex items-center gap-2">
                      <FileCode className="w-4 h-4" />
                      <span>{selectedPreview.code_diff.file_path}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs font-mono">
                      <span className="text-emerald-400 flex items-center gap-1">
                        <Check className="w-3.5 h-3.5" /> AST Validated
                      </span>
                      <span className="text-cyan-400">
                        WCAG 2.1 AA Score: {selectedPreview.code_diff.wcag_score}/100
                      </span>
                    </div>
                  </div>

                  {/* Unified Diff Box */}
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs overflow-x-auto leading-relaxed">
                    {selectedPreview.code_diff.diff_unified.split("\n").map((line, idx) => {
                      const isAdd = line.startsWith("+") && !line.startsWith("+++");
                      const isDel = line.startsWith("-") && !line.startsWith("---");
                      const isHeader = line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++");

                      return (
                        <div
                          key={idx}
                          className={`px-2 py-0.5 rounded ${
                            isAdd
                              ? "bg-emerald-950/40 text-emerald-300"
                              : isDel
                              ? "bg-rose-950/40 text-rose-300 line-through opacity-75"
                              : isHeader
                              ? "text-indigo-400 font-bold"
                              : "text-slate-400"
                          }`}
                        >
                          {line}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {selectedPreview.preview_type === "spend" && selectedPreview.spend_proposal && (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-slate-400 flex items-center gap-1.5">
                        <DollarSign className="w-4 h-4 text-emerald-400" />
                        <span>Proposed Budget Allocation</span>
                      </div>
                      <div className="text-lg font-bold font-mono text-amber-400">
                        ${selectedPreview.spend_proposal.total_spend.toLocaleString()} USD
                      </div>
                    </div>

                    <div className="space-y-2 pt-2 border-t border-slate-900 text-xs">
                      {Object.entries(selectedPreview.spend_proposal.channel_allocations).map(([ch, val]) => (
                        <div key={ch} className="flex justify-between font-mono text-slate-300">
                          <span className="capitalize">{ch.replace(/_/g, " ")}:</span>
                          <span className="text-emerald-400">${Number(val).toLocaleString()}</span>
                        </div>
                      ))}
                    </div>

                    <div className="pt-2 border-t border-slate-900 text-xs flex justify-between text-slate-400">
                      <span>Projected Marginal ROAS:</span>
                      <span className="font-mono text-indigo-400 font-bold">
                        {selectedPreview.spend_proposal.marginal_roas_projection}x
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Cryptographic Decision Signature Panel */}
              <div className="p-5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-white font-semibold text-xs">
                    <KeyRound className="w-4 h-4 text-indigo-400" />
                    <span>Cryptographic Sign-Off Certificate</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">
                    W3C PROV Signed Token Required
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Authorized Signer</label>
                    <input
                      type="text"
                      value={approverName}
                      onChange={(e) => setApproverName(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Role / Governance Authority</label>
                    <input
                      type="text"
                      value={approverRole}
                      onChange={(e) => setApproverRole(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-slate-400 mb-1">Revision / Audit Notes (Optional)</label>
                  <input
                    type="text"
                    value={revisionNotes}
                    onChange={(e) => setRevisionNotes(e.target.value)}
                    placeholder="Provide justification or required changes if rejecting/revising..."
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200"
                  />
                </div>

                {/* State Feedback if already decided */}
                {currentDecision && (
                  <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-800/60 text-xs space-y-1">
                    <div className="text-emerald-300 font-semibold flex items-center gap-1.5">
                      <FileCheck2 className="w-4 h-4 text-emerald-400" />
                      <span>Signature Registered: {currentDecision.decision}</span>
                    </div>
                    <div className="font-mono text-[10px] text-slate-400 truncate">
                      SHA256 Token: {currentDecision.hash}
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex flex-wrap items-center gap-3 pt-2">
                  <button
                    onClick={() => handleDecision("APPROVE")}
                    disabled={isSubmitting}
                    className="flex-1 py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/30 transition-all"
                  >
                    <Check className="w-4 h-4" />
                    <span>Approve & Authorize Dispatch</span>
                  </button>

                  <button
                    onClick={() => handleDecision("REQUEST_REVISION")}
                    disabled={isSubmitting}
                    className="py-2.5 px-4 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-2 transition-all"
                  >
                    <RefreshCw className="w-4 h-4" />
                    <span>Request Revision</span>
                  </button>

                  <button
                    onClick={() => handleDecision("REJECT")}
                    disabled={isSubmitting}
                    className="py-2.5 px-4 rounded-xl bg-rose-700 hover:bg-rose-600 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-2 transition-all"
                  >
                    <X className="w-4 h-4" />
                    <span>Reject</span>
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
