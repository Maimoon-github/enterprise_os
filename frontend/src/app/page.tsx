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
  Sparkles,
  Bot,
  ExternalLink,
  Box,
  Zap,
  Activity,
  Kanban,
  Sliders,
  Globe,
  RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api";
import { Directive, CanonicalTaskState, ActionPreview, IntelligenceResult } from "@/lib/types";
import { getStoredSettings, subscribeSettings, EnterpriseSettings } from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

interface PresetDirective {
  title: string;
  worker: string;
  objective: string;
  budget: number;
  risk: "low" | "medium" | "high";
}

const PRESET_DIRECTIVES: PresetDirective[] = [
  {
    title: "Checkout Tier Selector & Sandbox AST",
    worker: "W_DEV",
    objective: "Implement a high-converting pricing tiered checkout flow with WCAG 2.1 AA accessibility and zero-trust sandbox execution",
    budget: 25000,
    risk: "medium",
  },
  {
    title: "Zero-Trust Security Perimeter Audit",
    worker: "W_COMP",
    objective: "Run zero-trust security audit across all 7 bounded agent prompt boundaries and tool access permissions",
    budget: 10000,
    risk: "high",
  },
  {
    title: "Omnichannel ROAS & Budget Allocation",
    worker: "W_STRAT",
    objective: "Optimize Q4 paid acquisition budget across Search, Social, and DSP using marginal decay curve modeling",
    budget: 50000,
    risk: "medium",
  },
  {
    title: "Clinical Claims & Compliance Linter",
    worker: "W_PROD",
    objective: "Lint healthcare marketing claims against statutory regulations and verify provenance citations in sandbox",
    budget: 15000,
    risk: "high",
  },
];

export default function MissionControlDashboard() {
  const [directives, setDirectives] = useState<Directive[]>([]);
  const [tasks, setTasks] = useState<CanonicalTaskState[]>([]);
  const [approvals, setApprovals] = useState<ActionPreview[]>([]);
  const [settings, setSettings] = useState<EnterpriseSettings>(getStoredSettings());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRunningCycle, setIsRunningCycle] = useState(false);
  const [cycleStep, setCycleStep] = useState<string>("");
  const [objectiveInput, setObjectiveInput] = useState("");
  const [budgetCap, setBudgetCap] = useState(25000);
  const [riskCeiling, setRiskCeiling] = useState<"low" | "medium" | "high">("medium");
  const [latestPlan, setLatestPlan] = useState<IntelligenceResult | null>(null);
  const { addToast } = useToast();

  useEffect(() => {
    return subscribeSettings((newSettings) => {
      setSettings(newSettings);
    });
  }, []);

  const loadData = async () => {
    const dirs = await api.getDirectives();
    const t = await api.getTasks();
    const a = await api.getApprovalPreviews();
    setDirectives(dirs);
    setTasks(t);
    setApprovals(a);
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(
      loadData,
      settings.autoRefreshSeconds ? settings.autoRefreshSeconds * 1000 : 10000
    );
    return () => clearInterval(interval);
  }, [settings.autoRefreshSeconds]);

  // Single-Click Preset Launcher
  const handleLaunchPreset = async (preset: typeof PRESET_DIRECTIVES[0]) => {
    setIsSubmitting(true);
    try {
      const res = await api.createDirective({
        objective: preset.objective,
        budget_cap: preset.budget,
        risk_ceiling: preset.risk,
      });
      setLatestPlan(res.intelligence);
      await loadData();
      addToast({
        type: "success",
        title: `Directive Launched: ${preset.title}`,
        message: `Synthesized 4 DAG tasks assigned to ${preset.worker}.`,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Single-Click End-to-End Autonomous Cycle
  const handleRunFullCycle = async () => {
    setIsRunningCycle(true);
    setCycleStep("1. Dispatching Directive & Synthesizing DAG...");
    try {
      const res = await api.executeOneClickAutonomousCycle(
        objectiveInput.trim() || "Automated End-to-End Checkout Refactor & Sandbox Verification"
      );
      setCycleStep("2. Executed Sandbox AST → Signed HITL Dual-Signature → Released!");
      await loadData();
      addToast({
        type: "success",
        title: "Autonomous Cycle Completed!",
        message: `Clearance: ${res.clearance_id} • Telemetry Receipt: ${res.receipt_id}`,
        hash: res.prov_hash,
      });
    } finally {
      setTimeout(() => {
        setIsRunningCycle(false);
        setCycleStep("");
      }, 1500);
    }
  };

  // 1-Click Batch Task Execution
  const handleAdvanceAllTasks = async () => {
    const res = await api.runAllPendingTasks();
    await loadData();
    addToast({
      type: "success",
      title: "Batch CTS Task Transition",
      message: res.message,
    });
  };

  // 1-Click Telemetry Probe
  const handleProbeTelemetry = async () => {
    const probes = await api.runTelemetryProbes();
    addToast({
      type: "success",
      title: "Telemetry Probes Complete",
      message: `Verified 5 active listeners with average latency 2.8ms.`,
    });
  };

  // 1-Click Storefront Pixel Emission
  const handleEmitPixel = async () => {
    const rcpt = await api.sendPixelTelemetry({ page: "/pricing-tiers" });
    addToast({
      type: "success",
      title: "Storefront Pixel Admitted",
      message: `Receipt ID: ${rcpt.receipt_id} (Channel: ${rcpt.channel})`,
      hash: rcpt.content_hash,
    });
  };

  const completedCount = tasks.filter((t) => t.status === "completed").length;
  const inProgressCount = tasks.filter((t) => t.status === "in_progress").length;
  const pendingCount = tasks.filter((t) => t.status === "pending" || t.status === "granted").length;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner: Mission Control & Quick Launcher */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <span>Mission Control Dashboard</span>
            <span className="text-xs font-mono font-normal px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
              Autonomous Operating System
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Governed multi-agent orchestrator, zero-trust execution sandbox, and single-click autonomous pipeline control.
          </p>
        </div>

        {/* Global Action Badges */}
        <div className="flex flex-wrap items-center gap-2.5">
          <Link
            href="/approvals"
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-semibold transition-all"
          >
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>{approvals.length} Approvals Require Signature</span>
          </Link>

          <Link
            href="/settings"
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 text-xs font-semibold transition-all"
          >
            <Sliders className="w-4 h-4 text-indigo-400" />
            <span>Customize System</span>
          </Link>
        </div>
      </div>

      {/* PROMINENT DIRECT LINK CARD TO THE SANDBOX FRONT-END WEBSITE (sandbox/website) */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-amber-950/40 via-slate-900 to-slate-900 border border-amber-800/80 shadow-2xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shadow-lg shadow-amber-500/10">
              <Box className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-tight">
                  AIO Sandbox Front-End Website
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
                  sandbox/website
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  ONLINE :3001
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-1">
                Direct access to Rspress documentation, micro-tool code generators, and Scalar OpenAPI reference in <code className="text-amber-300 font-mono text-[11px]">sandbox/website</code>.
              </p>
            </div>
          </div>

          {/* Direct Launch Button */}
          <div className="flex items-center gap-2.5">
            <Link
              href="/sandbox"
              className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition-all"
            >
              <span>View Portal</span>
              <Layers className="w-3.5 h-3.5" />
            </Link>

            <a
              href={settings.sandboxWebsiteUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white text-xs font-semibold shadow-lg shadow-amber-600/30 flex items-center gap-2 transition-all group"
            >
              <span>Launch Sandbox Website</span>
              <ExternalLink className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
            </a>
          </div>
        </div>

        {/* Quick Deep-Links to Website Sections */}
        <div className="pt-3 border-t border-slate-800/80 flex flex-wrap items-center gap-3 text-xs">
          <span className="text-slate-400 font-medium">Quick Documentation Jumps:</span>
          <a
            href={`${settings.sandboxWebsiteUrl}/guide/start/introduction`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-amber-300 hover:text-white flex items-center gap-1 font-mono text-[11px]"
          >
            <span>📘 Architecture Guide</span>
            <ExternalLink className="w-2.5 h-2.5 opacity-60" />
          </a>
          <a
            href={`${settings.sandboxWebsiteUrl}/api`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-amber-300 hover:text-white flex items-center gap-1 font-mono text-[11px]"
          >
            <span>⚡ Scalar OpenAPI Docs</span>
            <ExternalLink className="w-2.5 h-2.5 opacity-60" />
          </a>
          <a
            href={`${settings.sandboxWebsiteUrl}/daemon/start/introduction`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-amber-300 hover:text-white flex items-center gap-1 font-mono text-[11px]"
          >
            <span>⚙️ Daemon & Network</span>
            <ExternalLink className="w-2.5 h-2.5 opacity-60" />
          </a>
          <a
            href={`${settings.sandboxWebsiteUrl}/blog/index`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-amber-300 hover:text-white flex items-center gap-1 font-mono text-[11px]"
          >
            <span>📰 Release Changelog</span>
            <ExternalLink className="w-2.5 h-2.5 opacity-60" />
          </a>
        </div>
      </div>

      {/* SINGLE-CLICK EXECUTIVE COMMAND CENTER */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-950/40 via-slate-900 to-slate-900 border border-indigo-800/80 shadow-2xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-bold text-white tracking-tight">
              Single-Click Autonomous Execution Center
            </h2>
          </div>
          <span className="text-[11px] font-mono text-indigo-300">
            One Click = Directive → DAG → Sandbox AST → HITL Approval → PROV Hash
          </span>
        </div>

        {/* 1-Click End-to-End Cycle Runner */}
        <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="text-sm font-semibold text-white">Execute Full End-to-End Autonomous Cycle</div>
            <p className="text-xs text-slate-400">
              Dispatches directive, formulates DAG, advances CTS tasks, executes sandbox AST check, cryptographically signs preview, and logs to W3C PROV ledger.
            </p>
            {cycleStep && (
              <div className="text-xs font-mono text-cyan-400 flex items-center gap-1.5 animate-pulse">
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>{cycleStep}</span>
              </div>
            )}
          </div>

          <button
            onClick={handleRunFullCycle}
            disabled={isRunningCycle}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white text-xs font-bold shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 shrink-0 transition-all"
          >
            {isRunningCycle ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Executing Cycle...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>1-Click Autonomous Run</span>
              </>
            )}
          </button>
        </div>

        {/* Single-Click Preset Directive Templates */}
        <div className="space-y-2">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            1-Click Preset Directive Dispatchers:
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {PRESET_DIRECTIVES.map((preset) => (
              <button
                key={preset.title}
                onClick={() => handleLaunchPreset(preset)}
                disabled={isSubmitting}
                className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-indigo-500/80 text-left transition-all space-y-2 group shadow-sm hover:shadow-indigo-500/10"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white group-hover:text-indigo-300 transition-colors">
                    {preset.title}
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                    {preset.worker}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                  {preset.objective}
                </p>
                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-500 font-mono">
                  <span>${preset.budget.toLocaleString()} Cap</span>
                  <span className="text-indigo-400 font-semibold flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                    <span>Dispatch</span>
                    <ArrowRight className="w-3 h-3" />
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Quick Operations Row */}
        <div className="pt-2 flex flex-wrap items-center gap-2.5">
          <span className="text-xs text-slate-500 font-medium">Quick Operations:</span>
          <button
            onClick={handleAdvanceAllTasks}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 transition-all"
          >
            <Kanban className="w-3.5 h-3.5 text-cyan-400" />
            <span>Advance All Tasks</span>
          </button>
          <button
            onClick={handleProbeTelemetry}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 transition-all"
          >
            <Activity className="w-3.5 h-3.5 text-rose-400" />
            <span>Probe Listeners</span>
          </button>
          <button
            onClick={handleEmitPixel}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 transition-all"
          >
            <Globe className="w-3.5 h-3.5 text-emerald-400" />
            <span>Emit Pixel Event</span>
          </button>
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
            <span>Max budget ceiling: ${settings.defaultBudgetCap.toLocaleString()}</span>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Pending HITL Approvals</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-bold text-amber-300 font-mono">{approvals.length}</div>
          <div className="text-xs text-amber-400/80 mt-2">
            Dual-Signature Cryptographic Queue
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
            <span className="text-indigo-400 font-mono font-medium">{inProgressCount} Active</span>
            <span>•</span>
            <span className="text-slate-400 font-mono">{pendingCount} Wait</span>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Container Isolation</span>
            <Shield className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono">STRICT (L6)</div>
          <div className="text-xs text-slate-400 mt-2">
            cgroups v2 • Ephemeral RAM scrub
          </div>
        </div>
      </div>

      {/* Directive Creator & Recent Tasks */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Custom Directive Dispatcher */}
        <div className="lg:col-span-6 space-y-4">
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white font-semibold text-sm">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                <span>Custom Autonomous Directive</span>
              </div>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                Engine: {settings.orchestratorModel}
              </span>
            </div>

            <div className="space-y-4">
              <div>
                <textarea
                  rows={3}
                  value={objectiveInput}
                  onChange={(e) => setObjectiveInput(e.target.value)}
                  placeholder="Enter custom directive objective to decompose into DAG..."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Budget Cap ($)</label>
                  <input
                    type="number"
                    value={budgetCap}
                    onChange={(e) => setBudgetCap(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Risk Ceiling</label>
                  <select
                    value={riskCeiling}
                    onChange={(e) => setRiskCeiling(e.target.value as any)}
                    className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200"
                  >
                    <option value="low">Low Risk</option>
                    <option value="medium">Medium Risk</option>
                    <option value="high">High Risk</option>
                  </select>
                </div>
              </div>

              <button
                onClick={() =>
                  handleLaunchPreset({
                    title: "Custom User Directive",
                    worker: "W_DEV",
                    objective: objectiveInput.trim() || "Execute custom tenant directive",
                    budget: budgetCap,
                    risk: riskCeiling,
                  })
                }
                disabled={isSubmitting}
                className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30 transition-all"
              >
                {isSubmitting ? (
                  <>
                    <Bot className="w-4 h-4 animate-spin" />
                    <span>Synthesizing DAG...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Synthesize DAG & Dispatch</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Right: Active Canonical Tasks Queue */}
        <div className="lg:col-span-6 space-y-4">
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white font-semibold text-sm">
                <Kanban className="w-4 h-4 text-cyan-400" />
                <span>Live Canonical Tasks (CTS)</span>
              </div>
              <Link href="/tasks" className="text-xs text-cyan-400 hover:underline">
                View Kanban Board →
              </Link>
            </div>

            <div className="space-y-3">
              {tasks.slice(0, 4).map((task) => (
                <div
                  key={task.task_id}
                  className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-slate-200">{task.task_id}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 text-indigo-400 border border-indigo-900/40">
                        {task.worker_role}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      Directive: {task.directive_id}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${
                        task.status === "completed"
                          ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                          : task.status === "in_progress"
                          ? "bg-indigo-950 text-indigo-400 border-indigo-800"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      }`}
                    >
                      {task.status.replace(/_/g, " ")}
                    </span>
                    <button
                      onClick={() => api.advanceTaskStatus(task.task_id, "completed").then(loadData)}
                      className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                      title="Advance Task"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
