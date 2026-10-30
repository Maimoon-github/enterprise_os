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
  };

  const pendingApprovals = approvals.filter((a) => a.status === "pending");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Human-in-the-Loop Approvals</h1>
          <p className="text-slate-400 text-sm">
            Review interrupted LangGraph runs, inspect diffs, and resume executions via Command(resume=...).
          </p>
        </div>
        <button
          onClick={() => fetchApprovals()}
          disabled={loading}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 rounded-lg transition"
        >
          {loading ? "Refreshing..." : "Refresh Queue"}
        </button>
      </div>

      {diffApproval && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">
              Blueprint Diff Inspection • Run {diffApproval.run_id}
            </h3>
            <button
              onClick={() => setDiffApproval(null)}
              className="text-xs text-slate-400 hover:text-slate-200"
            >
              Close Diff
            </button>
          </div>
          <DiffViewer
            beforeText={JSON.stringify(
              (diffApproval.payload as any)?.campaign_blueprint || {},
              null,
              2
            )}
            afterText={JSON.stringify(
              {
                ...(diffApproval.payload as any)?.campaign_blueprint,
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
        {loading && pendingApprovals.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500 bg-slate-900 border border-slate-800 rounded-xl">
            Loading pending approvals...
          </div>
        ) : pendingApprovals.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500 bg-slate-900 border border-slate-800 rounded-xl">
            No pending human approvals in the queue. All LangGraph runs are running or finalized.
          </div>
        ) : (
          pendingApprovals.map((appr) => (
            <ApprovalCard
              key={appr.id}
              approval={appr}
              onApprove={handleApprove}
              onReject={handleReject}
              onInspectDiff={(a) => setDiffApproval(a)}
            />
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
