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
} from "lucide-react";
import { api, MOCK_DIRECTIVES } from "@/lib/api";
import { Directive, PlanStep, IntelligenceResult } from "@/lib/types";

export default function DirectivesPage() {
  const [directives, setDirectives] = useState<any[]>(MOCK_DIRECTIVES);
  const [selectedDirective, setSelectedDirective] = useState<any>(MOCK_DIRECTIVES[0]);
  const [objective, setObjective] = useState("");
  const [budget, setBudget] = useState(20000);
  const [risk, setRisk] = useState("medium");
  const [isPlanning, setIsPlanning] = useState(false);

  useEffect(() => {
    const fetchDirs = async () => {
      const data = await api.getDirectives();
      if (data && data.length > 0) {
        setDirectives(data);
        if (!selectedDirective) setSelectedDirective(data[0]);
      }
    };
    fetchDirs();
  }, []);

  const handleCreateDirective = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!objective.trim()) return;

    setIsPlanning(true);
    try {
      const res = await api.createDirective({
        objective,
        budget_cap: budget,
        risk_ceiling: risk,
      });

      const newDir = {
        directive_id: res.directive_id,
        tenant_id: "tenant-enterprise-live",
        objective,
        budget_cap: budget,
        risk_ceiling: risk as any,
        scope: {
          tenant_id: "tenant-enterprise-live",
          brand_ids: ["brand-enterprise"],
          allowed_channels: ["web"],
        },
        created_at: new Date().toISOString(),
        intelligence: res.intelligence,
      };

      setDirectives([newDir, ...directives]);
      setSelectedDirective(newDir);
      setObjective("");
    } finally {
      setIsPlanning(false);
    }
  };

  const currentIntelligence: IntelligenceResult | undefined = selectedDirective?.intelligence;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
          <GitBranch className="w-6 h-6 text-indigo-400" />
          <span>Directives & Intelligence DAG Planning</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Formulate organizational objectives, enforce cognitive semantic constraints, and view deterministic DAG step dependencies.
        </p>
      </div>

      {/* Directive Creator Form */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-white font-semibold text-sm">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <span>Formulate Autonomous Directive</span>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
            Engine: Ollama Qwen 2.5 7B
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
                onChange={(e) => setRisk(e.target.value)}
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
                className="w-full py-2 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30"
              >
                {isPlanning ? (
                  <>
                    <Bot className="w-4 h-4 animate-spin" />
                    <span>Synthesizing DAG...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Run Planning Engine</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Main Split: Directive Selector & DAG Visualizer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Directive List */}
        <div className="lg:col-span-4 space-y-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
            Existing Directives ({directives.length})
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
                      ? "bg-indigo-950/40 border-indigo-500/50 shadow-md shadow-indigo-500/10"
                      : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-xs font-bold text-indigo-400">
                      {dir.directive_id}
                    </span>
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${
                        dir.risk_ceiling === "high"
                          ? "bg-rose-950/60 text-rose-400 border-rose-800"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      }`}
                    >
                      {dir.risk_ceiling} Risk
                    </span>
                  </div>
                  <p className="text-xs text-slate-200 line-clamp-2 leading-relaxed">
                    {dir.objective}
                  </p>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono mt-3 pt-2 border-t border-slate-800/80">
                    <span>${dir.budget_cap?.toLocaleString()} cap</span>
                    <span>{dir.created_at ? new Date(dir.created_at).toLocaleDateString() : "Live"}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Selected Directive Intelligence DAG Breakdown */}
        <div className="lg:col-span-8 space-y-6">
          {selectedDirective && (
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-6">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-indigo-400 font-semibold">
                    {selectedDirective.directive_id}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    Tenant: {selectedDirective.tenant_id}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-white leading-snug">
                  {selectedDirective.objective}
                </h2>
              </div>

              {currentIntelligence ? (
                <div className="space-y-6">
                  {/* Cognitive Rationale Box */}
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-semibold text-indigo-300 flex items-center gap-1.5">
                        <Bot className="w-3.5 h-3.5 text-indigo-400" />
                        <span>Cognitive Rationale Summary</span>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                        Confidence: {(currentIntelligence.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {currentIntelligence.rationale_summary}
                    </p>
                  </div>

                  {/* DAG Step Sequence */}
                  <div className="space-y-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                      Sequential Execution Plan (Directed Acyclic Graph)
                    </div>

                    <div className="space-y-3 relative before:absolute before:left-4 before:top-4 before:bottom-4 before:w-0.5 before:bg-indigo-900/40">
                      {currentIntelligence.plan.map((step, idx) => (
                        <div
                          key={step.step_id}
                          className="relative pl-10 group"
                        >
                          {/* Node Icon */}
                          <div className="absolute left-2 top-3 w-5 h-5 -ml-0.5 rounded-full bg-slate-900 border-2 border-indigo-500 flex items-center justify-center text-[10px] font-mono font-bold text-indigo-300 shadow-md shadow-indigo-500/20">
                            {idx + 1}
                          </div>

                          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/90 group-hover:border-indigo-500/50 transition-all space-y-2.5">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-bold text-indigo-400">
                                  {step.step_id}
                                </span>
                                <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-indigo-950/80 text-cyan-300 border border-cyan-800/50 font-mono">
                                  {step.recommended_worker || "UNASSIGNED"}
                                </span>
                              </div>
                              {step.dependencies.length > 0 && (
                                <div className="text-[11px] font-mono text-slate-500">
                                  Depends on: <span className="text-slate-300">{step.dependencies.join(", ")}</span>
                                </div>
                              )}
                            </div>

                            <p className="text-sm text-slate-200">{step.description}</p>

                            <div className="pt-2 border-t border-slate-900 flex flex-wrap items-center justify-between text-[11px] text-slate-400 gap-2">
                              <div>
                                <span className="text-slate-500">Output: </span>
                                <span className="font-mono text-slate-300">{step.expected_output}</span>
                              </div>
                              {step.context_requirements.length > 0 && (
                                <div className="font-mono text-[10px] text-slate-500">
                                  Reqs: {step.context_requirements.join(", ")}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center rounded-xl bg-slate-950/50 border border-slate-800 text-slate-400 text-xs">
                  No automated plan generated yet for this directive. Dispatch above to trigger Qwen 2.5 intelligence planning.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
