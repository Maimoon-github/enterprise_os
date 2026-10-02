"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
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
  ArrowRight,
  Code2,
  Lock,
} from "lucide-react";
import { api, MOCK_APPROVAL_PREVIEWS } from "@/lib/api";
import {
  ActionPreview,
  ApprovalDecisionRequest,
  DevelopmentDecisionRequest,
  DevelopmentDecisionResponse,
} from "@/lib/types";
import { getStoredSettings, EnterpriseSettings } from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

interface MockDevItem {
  task_id: string;
  workflow_id: string;
  step_id: string;
  attempt_id: string;
  subagent_id: string;
  component_name: string;
  description: string;
  input_snapshot_hash: string;
  output_snapshot_hash: string;
  review_dossier_hash: string;
  diff_unified: string;
  ast_metrics: {
    ast_valid: boolean;
    node_count: number;
    function_count: number;
    class_count: number;
  };
}

const MOCK_DEV_ITEMS: MockDevItem[] = [
  {
    task_id: "task-p2-checkout-pricing",
    workflow_id: "wf-ent-checkout-9021",
    step_id: "P2",
    attempt_id: "att-dev-001",
    subagent_id: "W_DEV_CODE_SYNTHESIS",
    component_name: "PricingTierSelector.tsx",
    description: "Multi-tiered checkout subscription component with WCAG 2.1 AA keyboard navigation and zero-trust sandbox execution",
    input_snapshot_hash: "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
    output_snapshot_hash: "sha256:4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
    review_dossier_hash: "sha256:99f8c0281b37dd190875e5332f1f56ff95b922a7f586a111a4c95973b065ec01",
    diff_unified: `--- a/components/PricingTierSelector.tsx
+++ b/components/PricingTierSelector.tsx
@@ -0,0 +1,24 @@
+import React from 'react';
+
+export interface PricingTier {
+  id: string;
+  name: string;
+  price: number;
+  features: string[];
+}
+
+export const PricingTierSelector = ({ tiers, onSelect }: { tiers: PricingTier[]; onSelect: (id: string) => void }) => {
+  return (
+    <div role="radiogroup" aria-label="Subscription tiers" className="grid grid-cols-1 md:grid-cols-3 gap-6">
+      {tiers.map((tier) => (
+        <div key={tier.id} className="p-6 rounded-2xl border border-slate-800 bg-slate-900/60 hover:border-cyan-500 transition-all">
+          <h3 className="text-lg font-bold text-white">{tier.name}</h3>
+          <p className="text-2xl font-mono text-cyan-400 mt-2">\${tier.price}/mo</p>
+          <button onClick={() => onSelect(tier.id)} className="w-full mt-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs">
+            Select {tier.name}
+          </button>
+        </div>
+      ))}
+    </div>
+  );
+};`,
    ast_metrics: {
      ast_valid: true,
      node_count: 48,
      function_count: 2,
      class_count: 0,
    },
  },
  {
    task_id: "task-s-code-patch-linter",
    workflow_id: "wf-sec-audit-8842",
    step_id: "S1",
    attempt_id: "att-dev-002",
    subagent_id: "W_DEV_CODE_LINTER",
    component_name: "BoundarySanitizer.py",
    description: "AST node sanitizer blocking eval, exec, and subprocess egress from unauthorized sub-agents",
    input_snapshot_hash: "sha256:1a82b9957fc1fa53c92dc18148a1d65dfc2d4b1fa3d677284addd200126d0012",
    output_snapshot_hash: "sha256:2c338888e4ee1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdab003",
    review_dossier_hash: "sha256:3d449999f5ff1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdab004",
    diff_unified: `--- a/security/BoundarySanitizer.py
+++ b/security/BoundarySanitizer.py
@@ -10,6 +10,12 @@
     def visit_Call(self, node):
+        forbidden = {"eval", "exec", "__import__", "compile"}
+        if isinstance(node.func, ast.Name) and node.func.id in forbidden:
+            raise SecurityBoundaryViolation(f"Forbidden call: {node.func.id}")
         self.generic_visit(node)`,
    ast_metrics: {
      ast_valid: true,
      node_count: 24,
      function_count: 1,
      class_count: 1,
    },
  },
];

export default function ApprovalsPage() {
  const [activeTab, setActiveTab] = useState<"previews" | "w_dev">("previews");
  const [previews, setPreviews] = useState<ActionPreview[]>(MOCK_APPROVAL_PREVIEWS);
  const [selectedPreview, setSelectedPreview] = useState<ActionPreview>(MOCK_APPROVAL_PREVIEWS[0]);
  const [settings] = useState<EnterpriseSettings>(getStoredSettings());
  const [approverName, setApproverName] = useState(settings.approverName);
  const [approverRole, setApproverRole] = useState(settings.approverRole);
  const [revisionNotes, setRevisionNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [decisionHistory, setDecisionHistory] = useState<Record<string, { decision: string; hash: string }>>({});

  // W_DEV Cryptographic Decision Sealing Studio State
  const [devItems] = useState<MockDevItem[]>(MOCK_DEV_ITEMS);
  const [selectedDevItem, setSelectedDevItem] = useState<MockDevItem>(MOCK_DEV_ITEMS[0]);
  const [devReviewerRole, setDevReviewerRole] = useState("engineering");
  const [devRevisionNotes, setDevRevisionNotes] = useState("");
  const [devSealedTokens, setDevSealedTokens] = useState<Record<string, DevelopmentDecisionResponse>>({});

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

      await api.submitApprovalDecision(selectedPreview.action_preview_id, payload);

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

  const handleDevDecision = async (decision: "APPROVE" | "REJECT" | "REQUEST_REVISION") => {
    if (!selectedDevItem) return;
    setIsSubmitting(true);

    try {
      const payload: DevelopmentDecisionRequest = {
        task_id: selectedDevItem.task_id,
        workflow_id: selectedDevItem.workflow_id,
        step_id: selectedDevItem.step_id,
        attempt_id: selectedDevItem.attempt_id,
        subagent_id: selectedDevItem.subagent_id,
        reviewer_id: approverName,
        reviewer_role: devReviewerRole,
        decision,
        input_snapshot_hash: selectedDevItem.input_snapshot_hash,
        output_snapshot_hash: selectedDevItem.output_snapshot_hash,
        review_dossier_hash: selectedDevItem.review_dossier_hash,
        signature: `ed25519-sig-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
        revision_notes: devRevisionNotes || undefined,
        machine_policy_allowed: true,
        expires_in_seconds: 7200,
      };

      const result = await api.decideDevelopment(payload);

      setDevSealedTokens((prev) => ({
        ...prev,
        [selectedDevItem.task_id]: result,
      }));

      addToast({
        type: decision === "APPROVE" ? "success" : decision === "REJECT" ? "error" : "warning",
        title: `W_DEV Decision Sealed: ${decision}`,
        message: `Token: ${result.token_id.slice(0, 16)}... | Signature: ${result.signature.slice(0, 14)}...`,
        hash: result.token_id,
      });
    } catch (err: any) {
      addToast({
        type: "error",
        title: "Cryptographic Sealing Error",
        message: err.message,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const currentDecision = selectedPreview ? decisionHistory[selectedPreview.action_preview_id] : null;
  const currentDevSealed = selectedDevItem ? devSealedTokens[selectedDevItem.task_id] : null;

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
          {activeTab === "previews" && (
            <button
              onClick={handleApproveAll}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-lg shadow-amber-600/20 transition-all font-mono"
            >
              <Zap className="w-3.5 h-3.5" />
              <span>1-Click Approve All Previews</span>
            </button>
          )}

          <Link
            href="/sandbox"
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-amber-950/40 hover:bg-amber-950/70 border border-amber-800/80 text-amber-300 text-xs font-semibold transition-all font-mono"
          >
            <Box className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>AIO Sandbox Daemon (:18091)</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>

      {/* Mode Tab Switcher */}
      <div className="flex items-center gap-2 p-1.5 rounded-xl bg-slate-900 border border-slate-800 w-fit">
        <button
          onClick={() => setActiveTab("previews")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
            activeTab === "previews"
              ? "bg-amber-600 text-white shadow-md shadow-amber-600/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <FileCheck2 className="w-3.5 h-3.5" />
          <span>Executive Action Previews ({previews.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("w_dev")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
            activeTab === "w_dev"
              ? "bg-cyan-600 text-white shadow-md shadow-cyan-600/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Code2 className="w-3.5 h-3.5" />
          <span>W_DEV Cryptographic Decision Sealing Studio ({devItems.length})</span>
        </button>
      </div>

      {/* TAB 1: EXECUTIVE ACTION PREVIEWS */}
      {activeTab === "previews" && (
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

                  <span className="font-mono text-xs px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300">
                    Tenant: {selectedPreview.tenant_id}
                  </span>
                </div>

                {/* Specific Payload Details */}
                {selectedPreview.spend_proposal && (
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-white">
                      <DollarSign className="w-4 h-4 text-emerald-400" />
                      <span>Spend Allocation Proposal</span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono text-xs">
                      <div>
                        <span className="text-slate-500 block">Total Spend</span>
                        <span className="text-white font-bold text-sm">
                          ${selectedPreview.spend_proposal.total_spend.toLocaleString()}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Projected ROAS</span>
                        <span className="text-emerald-400 font-bold text-sm">
                          {selectedPreview.spend_proposal.marginal_roas_projection}x
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {selectedPreview.code_diff && (
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-xs font-semibold text-white">
                        <FileCode className="w-4 h-4 text-cyan-400" />
                        <span>Code Modification Diff ({selectedPreview.code_diff.file_path})</span>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                        AST Validated
                      </span>
                    </div>
                    <pre className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-200 overflow-x-auto">
                      {selectedPreview.code_diff.diff_unified}
                    </pre>
                  </div>
                )}

                {/* Cryptographic Decision Interface */}
                <div className="p-5 rounded-xl bg-slate-950/80 border border-amber-800/40 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-amber-300">
                      <KeyRound className="w-4 h-4" />
                      <span>Cryptographic Authorization Signer</span>
                    </div>
                    {currentDecision && (
                      <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1.5">
                        <Check className="w-3.5 h-3.5" />
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
                      className="py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/30 transition-all font-mono"
                    >
                      <Check className="w-4 h-4" />
                      <span>1-Click Sign & Approve</span>
                    </button>

                    <button
                      onClick={() => handleDecision("REQUEST_REVISION")}
                      disabled={isSubmitting}
                      className="py-2.5 px-4 rounded-xl bg-amber-600/80 hover:bg-amber-600 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all font-mono"
                    >
                      <Clock className="w-4 h-4" />
                      <span>Request Revision</span>
                    </button>

                    <button
                      onClick={() => handleDecision("REJECT")}
                      disabled={isSubmitting}
                      className="py-2.5 px-4 rounded-xl bg-rose-600/80 hover:bg-rose-600 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all font-mono"
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
      )}

      {/* TAB 2: W_DEV CRYPTOGRAPHIC DECISION SEALING STUDIO */}
      {activeTab === "w_dev" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left: Pending W_DEV Deliverables */}
          <div className="lg:col-span-4 space-y-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
              Development Sub-Agent Deliverables ({devItems.length})
            </div>

            <div className="space-y-3">
              {devItems.map((item) => {
                const isSelected = selectedDevItem?.task_id === item.task_id;
                const token = devSealedTokens[item.task_id];

                return (
                  <button
                    key={item.task_id}
                    onClick={() => setSelectedDevItem(item)}
                    className={`w-full text-left p-4 rounded-xl border transition-all ${
                      isSelected
                        ? "bg-cyan-950/30 border-cyan-500/50 shadow-md shadow-cyan-500/10"
                        : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-xs font-bold text-slate-200">
                        {item.component_name}
                      </span>
                      <span
                        className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border font-mono ${
                          token
                            ? token.approved
                              ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                              : "bg-rose-950 text-rose-400 border-rose-800"
                            : "bg-cyan-950/60 text-cyan-400 border-cyan-800"
                        }`}
                      >
                        {token ? token.decision : "NEEDS SEAL"}
                      </span>
                    </div>

                    <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                      {item.description}
                    </p>

                    <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono mt-3 pt-2 border-t border-slate-800/80">
                      <span>Step {item.step_id}</span>
                      <span className="text-cyan-400">{item.subagent_id}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: Cryptographic Review Dossier & Sealer */}
          <div className="lg:col-span-8 space-y-6">
            {selectedDevItem && (
              <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-6">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-xs text-cyan-400 font-semibold">
                        {selectedDevItem.task_id}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">
                        Attempt: {selectedDevItem.attempt_id}
                      </span>
                    </div>
                    <h2 className="text-base font-bold text-white">
                      W_DEV Artifact: {selectedDevItem.component_name}
                    </h2>
                  </div>

                  <span className="font-mono text-xs px-2.5 py-1 rounded bg-cyan-950/60 border border-cyan-800 text-cyan-300">
                    Endpoint: /approvals/development/decide
                  </span>
                </div>

                {/* AST & Static Analysis Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block">AST Status</span>
                    <span className="text-emerald-400 font-bold">
                      {selectedDevItem.ast_metrics.ast_valid ? "VALID AST" : "INVALID"}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block">AST Nodes</span>
                    <span className="text-cyan-300 font-bold">
                      {selectedDevItem.ast_metrics.node_count}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block">Functions</span>
                    <span className="text-indigo-300 font-bold">
                      {selectedDevItem.ast_metrics.function_count}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block">Classes</span>
                    <span className="text-purple-300 font-bold">
                      {selectedDevItem.ast_metrics.class_count}
                    </span>
                  </div>
                </div>

                {/* Snapshot Cryptographic Hashes */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 font-mono text-xs">
                  <div className="flex items-center gap-2 text-slate-300 font-semibold mb-2">
                    <Lock className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Cryptographic Lineage Hashes (W3C PROV Bound)</span>
                  </div>
                  <div className="space-y-1.5 text-[11px]">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">Input Snapshot:</span>
                      <span className="text-slate-300">{selectedDevItem.input_snapshot_hash}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">Output Snapshot:</span>
                      <span className="text-slate-300">{selectedDevItem.output_snapshot_hash}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">Review Dossier:</span>
                      <span className="text-cyan-300">{selectedDevItem.review_dossier_hash}</span>
                    </div>
                  </div>
                </div>

                {/* Unified Code Diff */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-300">Generated Code Diff</span>
                    <span className="text-[10px] font-mono text-slate-500">Zero-trust cgroups sandbox pass</span>
                  </div>
                  <pre className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-200 overflow-x-auto max-h-56">
                    {selectedDevItem.diff_unified}
                  </pre>
                </div>

                {/* Sealed Token Result Banner */}
                {currentDevSealed && (
                  <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-700/60 space-y-2 font-mono text-xs">
                    <div className="flex items-center justify-between text-emerald-400 font-bold">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-emerald-400" />
                        <span>CRYPTOGRAPHICALLY SEALED & RECORDED TO PERSISTENCE</span>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-emerald-900/60 border border-emerald-600 text-white text-[10px]">
                        TOKEN VERIFIED
                      </span>
                    </div>
                    <div className="space-y-1 text-[11px] text-slate-300">
                      <div>Token ID: <span className="text-emerald-300">{currentDevSealed.token_id}</span></div>
                      <div>Signature: <span className="text-slate-400">{currentDevSealed.signature}</span></div>
                      <div>Reviewer: <span className="text-white">{currentDevSealed.reviewer_id} ({currentDevSealed.reviewer_role})</span></div>
                      <div>Expires At: <span className="text-slate-400">{currentDevSealed.expires_at}</span></div>
                    </div>
                  </div>
                )}

                {/* Reviewer Action Controls */}
                <div className="p-5 rounded-xl bg-slate-950/80 border border-cyan-800/40 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-cyan-300">
                      <KeyRound className="w-4 h-4" />
                      <span>W_DEV Ed25519 Cryptographic Decision Seal</span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400">Ed25519 Signature Auto-Generated</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Reviewer Identity</label>
                      <input
                        type="text"
                        value={approverName}
                        onChange={(e) => setApproverName(e.target.value)}
                        className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1">Reviewer Role</label>
                      <select
                        value={devReviewerRole}
                        onChange={(e) => setDevReviewerRole(e.target.value)}
                        className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 font-mono"
                      >
                        <option value="engineering">engineering (Lead Engineer)</option>
                        <option value="security">security (SecOps Lead)</option>
                        <option value="compliance">compliance (Legal & Compliance)</option>
                        <option value="admin">admin (Platform Administrator)</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Revision / Review Notes (Optional)</label>
                    <input
                      type="text"
                      value={devRevisionNotes}
                      onChange={(e) => setDevRevisionNotes(e.target.value)}
                      placeholder="Enter verification notes or required code alterations..."
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200"
                    />
                  </div>

                  {/* 1-Click Action Buttons */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                    <button
                      onClick={() => handleDevDecision("APPROVE")}
                      disabled={isSubmitting}
                      className="py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/30 transition-all font-mono"
                    >
                      <ShieldCheck className="w-4 h-4" />
                      <span>Seal & Approve (Ed25519)</span>
                    </button>

                    <button
                      onClick={() => handleDevDecision("REQUEST_REVISION")}
                      disabled={isSubmitting}
                      className="py-2.5 px-4 rounded-xl bg-amber-600/80 hover:bg-amber-600 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all font-mono"
                    >
                      <Clock className="w-4 h-4" />
                      <span>Request Revision</span>
                    </button>

                    <button
                      onClick={() => handleDevDecision("REJECT")}
                      disabled={isSubmitting}
                      className="py-2.5 px-4 rounded-xl bg-rose-600/80 hover:bg-rose-600 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all font-mono"
                    >
                      <X className="w-4 h-4" />
                      <span>Reject Artifact</span>
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
