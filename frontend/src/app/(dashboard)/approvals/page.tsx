"use client";

import { useEffect, useState } from "react";
import { ApprovalCard } from "@/components/approvals/approval-card";
import { DiffViewer } from "@/components/approvals/diff-viewer";
import { ResumeDialog } from "@/components/approvals/resume-dialog";
import { useApprovals } from "@/hooks/use-approvals";
import { ApprovalResponse } from "@marketing-os/contracts";

export default function ApprovalsQueuePage() {
  const { approvals, fetchApprovals, resume, loading } = useApprovals();
  const [selectedApproval, setSelectedApproval] = useState<ApprovalResponse | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isApprovalAction, setIsApprovalAction] = useState(true);
  const [diffApproval, setDiffApproval] = useState<ApprovalResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"pending" | "all">("pending");

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const handleApprove = (id: string) => {
    const appr = approvals.find((a) => a.id === id);
    if (appr) {
      setSelectedApproval(appr);
      setIsApprovalAction(true);
      setIsDialogOpen(true);
    }
  };

  const handleReject = (id: string) => {
    const appr = approvals.find((a) => a.id === id);
    if (appr) {
      setSelectedApproval(appr);
      setIsApprovalAction(false);
      setIsDialogOpen(true);
    }
  };

  const handleDialogSubmit = async (notes: string, approved: boolean) => {
    if (!selectedApproval) return;
    await resume(selectedApproval.id, approved, notes);
    setIsDialogOpen(false);
    setSelectedApproval(null);
    await fetchApprovals();
  };

  const pendingApprovals = approvals.filter((a) => a.status === "pending");
  const displayApprovals = activeTab === "pending" ? pendingApprovals : approvals;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-bloodstone-text">Human-in-the-Loop Approvals</h1>
          <p className="text-bloodstone-text-muted text-sm">
            Review interrupted LangGraph runs, inspect diffs, and resume executions via Command(resume=...).
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex bg-glass-base border border-glass-subtle rounded-lg p-0.5 text-xs font-medium">
            <button
              onClick={() => setActiveTab("pending")}
              className={`px-3 py-1.5 rounded-md transition duration-fast ease-out-expo ${
                activeTab === "pending"
                  ? "bg-glass-emerald border border-glass-specular text-bloodstone-mint shadow-bloodstone-glow"
                  : "text-bloodstone-text-muted hover:text-bloodstone-text"
              }`}
            >
              Pending ({pendingApprovals.length})
            </button>
            <button
              onClick={() => setActiveTab("all")}
              className={`px-3 py-1.5 rounded-md transition duration-fast ease-out-expo ${
                activeTab === "all"
                  ? "bg-glass-emerald border border-glass-specular text-bloodstone-mint shadow-bloodstone-glow"
                  : "text-bloodstone-text-muted hover:text-bloodstone-text"
              }`}
            >
              All ({approvals.length})
            </button>
          </div>
          <button
            onClick={() => fetchApprovals()}
            disabled={loading}
            className="px-3.5 py-1.5 bg-glass-base hover:bg-glass-elevated border border-glass-subtle text-xs font-semibold text-bloodstone-text rounded-lg transition duration-fast ease-out-expo"
          >
            {loading ? "Refreshing..." : "Refresh Queue"}
          </button>
        </div>
      </div>

      {diffApproval && (
        <div className="glass-panel-elevated rounded-xl p-6 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-bloodstone-text">
              Blueprint Diff Inspection • Run {diffApproval.run_id}
            </h3>
            <button
              onClick={() => setDiffApproval(null)}
              className="text-xs text-bloodstone-text-muted hover:text-bloodstone-text"
            >
              Close Diff
            </button>
          </div>
          <DiffViewer
            beforeText={JSON.stringify(
              (diffApproval.payload as any)?.campaign_blueprint || diffApproval.payload || {},
              null,
              2
            )}
            afterText={JSON.stringify(
              {
                ...((diffApproval.payload as any)?.campaign_blueprint || diffApproval.payload),
                reviewed_with_compliance: true,
                target_state: "execute_platform_publish_node",
              },
              null,
              2
            )}
          />
        </div>
      )}

      <div className="space-y-4">
        {loading && approvals.length === 0 ? (
          <div className="p-8 text-center text-sm text-bloodstone-text-muted glass-panel rounded-xl">
            Loading approval requests from database...
          </div>
        ) : displayApprovals.length === 0 ? (
          <div className="p-8 text-center text-sm text-bloodstone-text-muted glass-panel rounded-xl">
            {activeTab === "pending"
              ? "No pending human approvals in the queue. All LangGraph runs are running or finalized."
              : "No approval records found."}
          </div>
        ) : (
          displayApprovals.map((appr) => (
            <div key={appr.id} className="space-y-2">
              <ApprovalCard
                approval={appr}
                onApprove={handleApprove}
                onReject={handleReject}
                onInspectDiff={(a) => setDiffApproval(a)}
              />
              {appr.status !== "pending" && appr.decision_notes && (
                <div className="mx-4 p-2.5 bg-slate-950 border border-slate-800/80 rounded-lg text-xs text-slate-400 flex items-center gap-2">
                  <span className="font-semibold text-slate-300">Decision Notes:</span>
                  <span>{appr.decision_notes}</span>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <ResumeDialog
        isOpen={isDialogOpen}
        approvalId={selectedApproval?.id}
        isApprovalAction={isApprovalAction}
        onClose={() => {
          setIsDialogOpen(false);
          setSelectedApproval(null);
        }}
        onResume={handleDialogSubmit}
      />
    </div>
  );
}
