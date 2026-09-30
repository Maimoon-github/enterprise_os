"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Compass,
  CheckCircle2,
  AlertTriangle,
  Play,
  ArrowRight,
  TrendingUp,
  Shield,
  Layers,
  Clock,
  Sparkles,
  Bot,
  ExternalLink,
  Box,
} from "lucide-react";
import { api, MOCK_APPROVAL_PREVIEWS } from "@/lib/api";
import { Directive, CanonicalTaskState, ActionPreview, IntelligenceResult } from "@/lib/types";

export default function MissionControlDashboard() {
  const [directives, setDirectives] = useState<Directive[]>([]);
  const [tasks, setTasks] = useState<CanonicalTaskState[]>([]);
  const [approvals, setApprovals] = useState<ActionPreview[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [objectiveInput, setObjectiveInput] = useState("");
  const [budgetCap, setBudgetCap] = useState(15000);
  const [riskCeiling, setRiskCeiling] = useState<"low" | "medium" | "high">("medium");
  const [latestPlan, setLatestPlan] = useState<IntelligenceResult | null>(null);

  useEffect(() => {
    const loadData = async () => {
      const dirs = await api.getDirectives();
      const t = await api.getTasks();
      const a = await api.getApprovalPreviews();
      setDirectives(dirs);
      setTasks(t);
      setApprovals(a);
    };
    loadData();
  }, []);

  const handleCreateDirective = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!objectiveInput.trim()) return;

    setIsSubmitting(true);
    try {
      const result = await api.createDirective({
        objective: objectiveInput,
        budget_cap: budgetCap,
        risk_ceiling: riskCeiling,
      });

      if (result.intelligence) {
        setLatestPlan(result.intelligence);
      }

      // Reload directives and tasks
      const dirs = await api.getDirectives();
      setDirectives(dirs);
      setObjectiveInput("");
    } finally {
      setIsSubmitting(false);
    }
  };

  const completedCount = tasks.filter((t) => t.status === "completed").length;
  const inProgressCount = tasks.filter((t) => t.status === "in_progress").length;
  const pendingCount = tasks.filter((t) => t.status === "pending" || t.status === "granted").length;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Page Title & Status Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            Mission Control Dashboard
            <span className="text-xs font-mono font-normal px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
              Autonomous v1.0
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time multi-agent execution monitor, zero-trust sandbox gatekeeper, and HITL authorization queue.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/approvals"
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-semibold transition-all"
          >
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>2 Approvals Require Signature</span>
          </Link>
          <Link
            href="/directives"
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all"
          >
            <Sparkles className="w-4 h-4" />
            <span>Formulate Plan DAG</span>
          </Link>
        </div>
      </div>

      {/* KPI Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Active Directives</span>
            <Compass className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-3xl font-bold text-white font-mono">{directives.length}</div>
          <div className="text-xs text-indigo-400/90 mt-2 flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Max budget ceiling: $35,000</span>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Pending HITL Approvals</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-bold text-amber-300 font-mono">{approvals.length}</div>
          <div className="text-xs text-amber-400/80 mt-2">
            1 Live Code Diff • 1 Spend Proposal
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Canonical Tasks (CTS)</span>
            <Layers className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-3xl font-bold text-white font-mono">{tasks.length}</div>
          <div className="text-xs text-slate-400 mt-2 flex items-center gap-2">
            <span className="text-emerald-400 font-mono font-medium">{completedCount} Done</span>
            <span>•</span>
            <span className="text-indigo-400 font-mono font-medium">{inProgressCount} In Flight</span>
            <span>•</span>
            <span className="text-slate-400 font-mono">{pendingCount} Wait</span>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">PROV Ledger Height</span>
            <Shield className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-bold text-emerald-400 font-mono">28</div>
          <div className="text-xs text-emerald-400/80 mt-2 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>SHA-256 Merkle chain verified</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Directive Formulation & Approvals Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Directive Formulation */}
        <div className="lg:col-span-7 space-y-6">
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
                  <Play className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-white">Live Directive Formulation</h2>
                  <p className="text-xs text-slate-400">Trigger Ollama Qwen 2.5 decomposition into sequential PlanSteps</p>
                </div>
              </div>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                POST /directives
              </span>
            </div>

            <form onSubmit={handleCreateDirective} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  High-Level Objective Prompt
                </label>
                <textarea
                  rows={3}
                  value={objectiveInput}
                  onChange={(e) => setObjectiveInput(e.target.value)}
                  placeholder="e.g. Build an accessible tiered checkout flow with Jest unit tests and AST syntax validation..."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all font-sans"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Budget Ceiling ($ USD)
                  </label>
                  <input
                    type="number"
                    value={budgetCap}
                    onChange={(e) => setBudgetCap(Number(e.target.value))}
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Risk Ceiling Constraint
                  </label>
                  <select
                    value={riskCeiling}
                    onChange={(e) => setRiskCeiling(e.target.value as any)}
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="low">Low (Standard Read/Write)</option>
                    <option value="medium">Medium (Code Modification)</option>
                    <option value="high">High (Production / Spend)</option>
                  </select>
                </div>
              </div>

              <div className="pt-2 flex items-center justify-between">
                <span className="text-xs text-slate-500">
                  Execution bounded inside isolated Docker sandbox
                </span>
                <button
                  type="submit"
                  disabled={isSubmitting || !objectiveInput.trim()}
                  className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-indigo-600/30 transition-all"
                >
                  {isSubmitting ? (
                    <>
                      <Bot className="w-4 h-4 animate-spin" />
                      <span>Synthesizing Plan...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Dispatch Directive</span>
                    </>
                  )}
                </button>
              </div>
            </form>

            {/* Generated Plan DAG Preview */}
            {latestPlan && (
              <div className="p-4 rounded-xl bg-indigo-950/20 border border-indigo-800/60 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-indigo-300 font-semibold text-xs">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Intelligence Plan Synthesized ({latestPlan.plan.length} Steps)</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-900/60 text-indigo-300 border border-indigo-700/60">
                    Confidence: {(latestPlan.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="space-y-2">
                  {latestPlan.plan.map((step) => (
                    <div
                      key={step.step_id}
                      className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs flex items-start gap-3"
                    >
                      <span className="font-mono font-bold text-indigo-400">{step.step_id}</span>
                      <div className="flex-1">
                        <div className="text-slate-200">{step.description}</div>
                        <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                          Worker: <span className="text-cyan-400">{step.recommended_worker || "AUTO"}</span> •
                          Output: {step.expected_output}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Active Canonical Tasks Overview */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Layers className="w-4 h-4 text-cyan-400" />
                <h2 className="text-base font-semibold text-white">Active Canonical Tasks (CTS)</h2>
              </div>
              <Link href="/tasks" className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                <span>View Full State Machine</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="divide-y divide-slate-800/80">
              {tasks.slice(0, 4).map((task) => (
                <div key={task.task_id} className="py-3 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs text-slate-400">{task.task_id}</span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700 font-mono">
                      {task.worker_role}
                    </span>
                    <span className="text-xs text-slate-300">v{task.version}</span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${
                        task.status === "completed"
                          ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                          : task.status === "in_progress"
                          ? "bg-indigo-950 text-indigo-400 border-indigo-800 animate-pulse"
                          : task.status === "granted"
                          ? "bg-cyan-950 text-cyan-400 border-cyan-800"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      }`}
                    >
                      {task.status}
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">
                      {task.updated_at ? new Date(task.updated_at).toLocaleTimeString() : "--"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Pending HITL Approvals & Action Previews */}
        <div className="lg:col-span-5 space-y-6">
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h2 className="text-base font-semibold text-white">Pending Action Previews</h2>
              </div>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                HITL Gatekeeper
              </span>
            </div>

            <p className="text-xs text-slate-400">
              Zero code execution or financial spend occurs until an authorized operator signs the cryptographic preview.
            </p>

            <div className="space-y-4">
              {approvals.map((prev) => (
                <div
                  key={prev.action_preview_id}
                  className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 space-y-3 hover:border-slate-700 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-medium text-slate-300">
                      {prev.action_preview_id}
                    </span>
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${
                        prev.risk_level === "high"
                          ? "bg-rose-950/60 text-rose-400 border-rose-800/80"
                          : "bg-amber-950/60 text-amber-400 border-amber-800/80"
                      }`}
                    >
                      {prev.risk_level} Risk
                    </span>
                  </div>

                  <p className="text-xs text-slate-200 line-clamp-2">{prev.summary}</p>

                  {prev.preview_type === "live_code_diff" && prev.code_diff && (
                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 font-mono text-[11px] text-slate-300">
                      <div className="text-indigo-400 mb-1 flex items-center justify-between">
                        <span>{prev.code_diff.file_path}</span>
                        <span className="text-emerald-400">AST Valid ✓</span>
                      </div>
                      <div className="text-slate-500 text-[10px]">WCAG Score: {prev.code_diff.wcag_score}/100</div>
                    </div>
                  )}

                  {prev.preview_type === "spend" && prev.spend_proposal && (
                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs">
                      <div className="flex justify-between text-slate-300 font-mono">
                        <span>Total Requested Spend:</span>
                        <span className="text-amber-400 font-bold">${prev.spend_proposal.total_spend.toLocaleString()}</span>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-1">
                        Marginal ROAS: {prev.spend_proposal.marginal_roas_projection}x
                      </div>
                    </div>
                  )}

                  <Link
                    href="/approvals"
                    className="w-full py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs font-semibold text-slate-200 flex items-center justify-center gap-1.5 transition-all"
                  >
                    <span>Inspect & Sign Decision</span>
                    <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                  </Link>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Agent Engine Monitor Link */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-indigo-950/40 via-slate-900/60 to-slate-950 border border-indigo-900/40 backdrop-blur-md flex items-center justify-between">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-white flex items-center gap-2">
                <Bot className="w-4 h-4 text-indigo-400" />
                <span>7 Bounded Agent Engines</span>
              </div>
              <p className="text-xs text-slate-400">
                Inspect OODA cognitive reasoning loop & sandbox logs
              </p>
            </div>
            <Link
              href="/workers"
              className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20 transition-all"
            >
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {/* Quick Sandbox Environment Link */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-amber-950/30 via-slate-900/60 to-slate-950 border border-amber-900/40 backdrop-blur-md flex items-center justify-between">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-white flex items-center gap-2">
                <Box className="w-4 h-4 text-amber-400" />
                <span>AIO Agent Sandbox Portal</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800">
                  :3001
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Isolated browser, shell, filesystem & synced website documentation
              </p>
            </div>
            <Link
              href="/sandbox"
              className="p-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white shadow-lg shadow-amber-600/20 transition-all"
            >
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
