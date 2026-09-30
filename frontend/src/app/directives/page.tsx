"use client";

import React, { useEffect, useState } from "react";
import {
  GitBranch,
  Sparkles,
  ArrowRight,
  Shield,
  Layers,
  CheckCircle,
  Clock,
  Bot,
  AlertCircle,
  FileCode,
  DollarSign,
  Play,
  Zap,
  Box,
  ExternalLink,
} from "lucide-react";
import { api, MOCK_DIRECTIVES } from "@/lib/api";
import { Directive, PlanStep, IntelligenceResult } from "@/lib/types";
import { getStoredSettings, EnterpriseSettings } from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

const PRESET_TEMPLATES = [
  {
    label: "Tiered Pricing Selector",
    worker: "W_DEV",
    objective: "Implement a high-converting pricing tiered checkout flow with WCAG 2.1 AA accessibility and zero-trust sandbox execution",
    budget: 25000,
    risk: "medium" as const,
  },
  {
    label: "Prompt Boundary Linter",
    worker: "W_COMP",
    objective: "Run zero-trust security audit across all 7 bounded agent prompt boundaries and tool access permissions",
    budget: 10000,
    risk: "high" as const,
  },
  {
    label: "Marginal ROAS Optimization",
    worker: "W_STRAT",
    objective: "Decompose portfolio ad spend into multi-touch attribution decay curves to maximize marginal blended return",
    budget: 35000,
    risk: "medium" as const,
  },
  {
    label: "Compliance Claim Attestation",
    worker: "W_PROD",
    objective: "Validate clinical assertions against statutory guidelines and generate cryptographically verifiable proof tokens",
    budget: 12000,
    risk: "high" as const,
  },
];

export default function DirectivesPage() {
  const [directives, setDirectives] = useState<any[]>(MOCK_DIRECTIVES);
  const [selectedDirective, setSelectedDirective] = useState<any>(MOCK_DIRECTIVES[0]);
  const [objective, setObjective] = useState("");
  const [budget, setBudget] = useState(25000);
  const [risk, setRisk] = useState<"low" | "medium" | "high">("medium");
  const [isPlanning, setIsPlanning] = useState(false);
  const [settings] = useState<EnterpriseSettings>(getStoredSettings());
  const { addToast } = useToast();

  const fetchDirs = async () => {
    const data = await api.getDirectives();
    if (data && data.length > 0) {
      setDirectives(data);
      if (!selectedDirective) setSelectedDirective(data[0]);
    }
  };

  useEffect(() => {
    fetchDirs();
  }, []);

  const handleCreateDirective = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!objective.trim()) return;

    setIsPlanning(true);
    try {
      const res = await api.createDirective({
        objective,
        budget_cap: budget,
        risk_ceiling: risk,
      });

      await fetchDirs();
      const updated = await api.getDirectives();
      const newest = updated.find((d) => d.directive_id === res.directive_id) || updated[0];
      setSelectedDirective(newest);
      setObjective("");
      addToast({
        type: "success",
        title: "Autonomous DAG Plan Synthesized",
        message: `Generated 4 sequential steps under ${risk} risk ceiling.`,
      });
    } finally {
      setIsPlanning(false);
    }
  };

  const handleApplyPreset = (preset: typeof PRESET_TEMPLATES[0]) => {
    setObjective(preset.objective);
    setBudget(preset.budget);
    setRisk(preset.risk);
    addToast({
      type: "info",
      title: `Loaded Template: ${preset.label}`,
      message: "Form populated. Click 'Synthesize DAG' or dispatch directly.",
    });
  };

  const currentIntelligence: IntelligenceResult | undefined = selectedDirective?.intelligence;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <GitBranch className="w-6 h-6 text-indigo-400" />
            <span>Directives & Intelligence DAG Planning</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Formulate organizational objectives, enforce cognitive semantic constraints, and view deterministic DAG step dependencies.
          </p>
        </div>

        {/* Sandbox Website Direct Link */}
        <a
          href={`${settings.sandboxWebsiteUrl}/guide/start/introduction`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-amber-950/40 hover:bg-amber-950/70 border border-amber-800/80 text-amber-300 text-xs font-semibold transition-all font-mono"
        >
          <Box className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
          <span>Sandbox Guide (:3001)</span>
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>

      {/* Preset 1-Click Template Selector */}
      <div className="space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
          1-Click Preset Directive Templates:
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {PRESET_TEMPLATES.map((p) => (
            <button
              key={p.label}
              onClick={() => handleApplyPreset(p)}
              className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-indigo-500/60 text-left transition-all space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">{p.label}</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                  {p.worker}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 line-clamp-2">{p.objective}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Directive Creator Form */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-white font-semibold text-sm">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <span>Formulate Autonomous Directive</span>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
            Engine: {settings.orchestratorModel}
          </span>
        </div>

        <form onSubmit={handleCreateDirective} className="space-y-4">
          <div>
            <textarea
              rows={2}
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="Enter high-level objective (e.g. Implement resilient token-refresh mechanism for tenant authentication with unit tests)..."
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Budget Ceiling ($)</label>
              <input
                type="number"
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Risk Ceiling</label>
              <select
                value={risk}
                onChange={(e) => setRisk(e.target.value as any)}
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200"
              >
                <option value="low">Low Risk (Standard)</option>
                <option value="medium">Medium Risk (Code Alteration)</option>
                <option value="high">High Risk (Production / Financial)</option>
              </select>
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={isPlanning || !objective.trim()}
                className="w-full py-2 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30 transition-all"
              >
                {isPlanning ? (
                  <>
                    <Bot className="w-4 h-4 animate-spin" />
                    <span>Synthesizing DAG...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Run Planning Engine (1-Click)</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Main Grid: Directives List & DAG Plan Visualizer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Active Directives Selector */}
        <div className="lg:col-span-5 space-y-3">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
            Active Enterprise Directives ({directives.length})
          </div>

          <div className="space-y-3">
            {directives.map((dir) => {
              const isSelected = selectedDirective?.directive_id === dir.directive_id;
              return (
                <button
                  key={dir.directive_id}
                  onClick={() => setSelectedDirective(dir)}
                  className={`w-full text-left p-4 rounded-xl border transition-all ${
                    isSelected
                      ? "bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-500/10"
                      : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-xs font-bold text-slate-200">
                      {dir.directive_id}
                    </span>
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${
                        dir.risk_ceiling === "high"
                          ? "bg-rose-950/60 text-rose-400 border-rose-800"
                          : dir.risk_ceiling === "medium"
                          ? "bg-amber-950/60 text-amber-400 border-amber-800"
                          : "bg-emerald-950/60 text-emerald-400 border-emerald-800"
                      }`}
                    >
                      {dir.risk_ceiling} Risk
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                    {dir.objective}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono mt-3 pt-2 border-t border-slate-800/80">
                    <span>${dir.budget_cap?.toLocaleString() || "0"} Budget</span>
                    <span className="text-indigo-400">
                      {dir.intelligence?.plan?.length || 0} Steps
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Selected Directive DAG Steps Visualizer */}
        <div className="lg:col-span-7 space-y-6">
          {selectedDirective && (
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-6">
              <div className="border-b border-slate-800 pb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs text-indigo-400 font-semibold">
                    {selectedDirective.directive_id}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    Tenant: {selectedDirective.tenant_id}
                  </span>
                </div>
                <h2 className="text-base font-bold text-white">
                  {selectedDirective.objective}
                </h2>
              </div>

              {currentIntelligence ? (
                <div className="space-y-6">
                  {/* Synthesis Metrics */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono text-xs">
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block">Intent Tag</span>
                      <span className="text-indigo-300 font-bold">{currentIntelligence.intent}</span>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block">Confidence</span>
                      <span className="text-emerald-400 font-bold">
                        {(currentIntelligence.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-slate-500 block">DAG Nodes</span>
                      <span className="text-cyan-400 font-bold">
                        {currentIntelligence.plan?.length || 0} Steps
                      </span>
                    </div>
                  </div>

                  {/* DAG Plan Steps */}
                  <div className="space-y-3">
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
                      Deterministic Execution Pipeline (DAG)
                    </span>

                    <div className="space-y-3 relative before:absolute before:left-4 before:top-4 before:bottom-4 before:w-0.5 before:bg-slate-800">
                      {currentIntelligence.plan?.map((step: PlanStep, idx: number) => (
                        <div key={step.step_id} className="relative pl-9 space-y-1">
                          {/* Step Marker */}
                          <div className="absolute left-2 top-3 w-4 h-4 -ml-0.5 rounded-full bg-slate-950 border-2 border-indigo-500 flex items-center justify-center text-[9px] font-mono text-indigo-300">
                            {idx + 1}
                          </div>

                          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="font-mono text-xs font-bold text-white">
                                {step.step_id}
                              </span>
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 font-semibold">
                                {step.recommended_worker || "UNASSIGNED"}
                              </span>
                            </div>

                            <p className="text-xs text-slate-300 leading-relaxed">
                              {step.description}
                            </p>

                            <div className="pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400">
                              <span>Output: {step.expected_output}</span>
                              {step.dependencies?.length > 0 && (
                                <span className="text-amber-400">
                                  Depends on: {step.dependencies.join(", ")}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-slate-500 text-xs">
                  No intelligence plan formulated for this directive.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
