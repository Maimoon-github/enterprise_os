"use client";

import React, { useState } from "react";
import {
  Bot,
  Brain,
  Cpu,
  Layers,
  Sparkles,
  Terminal,
  Activity,
  CheckCircle,
  Eye,
  Compass,
  Zap,
} from "lucide-react";
import { MOCK_WORKER_ROSTER } from "@/lib/api";
import { WorkerRole } from "@/lib/types";

export default function WorkersPage() {
  const [roster, setRoster] = useState(MOCK_WORKER_ROSTER);
  const [selectedRole, setSelectedRole] = useState<WorkerRole>("W_DEV");

  const currentWorker = roster.find((w) => w.role === selectedRole) || roster[0];

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
          <Bot className="w-6 h-6 text-emerald-400" />
          <span>7 Bounded Worker Engines & Cognitive Stream</span>
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Zero-trust agent sandbox boundaries. Each bounded agent operates under explicit prompt restrictions and immutable role policies.
        </p>
      </div>

      {/* Grid: Worker List & Cognitive Stream Visualizer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Worker Roster */}
        <div className="lg:col-span-5 space-y-3">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
            Specialized Bounded Engines ({roster.length})
          </div>

          <div className="space-y-3">
            {roster.map((worker) => {
              const isSelected = selectedRole === worker.role;

              return (
                <button
                  key={worker.role}
                  onClick={() => setSelectedRole(worker.role)}
                  className={`w-full text-left p-4 rounded-xl border transition-all ${
                    isSelected
                      ? "bg-emerald-950/30 border-emerald-500/50 shadow-md shadow-emerald-500/10"
                      : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-emerald-400">
                        {worker.role}
                      </span>
                      <span className="text-sm font-semibold text-white">
                        {worker.name}
                      </span>
                    </div>

                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border ${
                        worker.activeStatus === "executing"
                          ? "bg-indigo-950 text-indigo-400 border-indigo-800 animate-pulse"
                          : worker.activeStatus === "thinking"
                          ? "bg-cyan-950 text-cyan-400 border-cyan-800"
                          : worker.activeStatus === "awaiting_approval"
                          ? "bg-amber-950 text-amber-400 border-amber-800"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      }`}
                    >
                      {worker.activeStatus.replace(/_/g, " ")}
                    </span>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">
                    {worker.specialization}
                  </p>

                  {worker.currentTask && (
                    <div className="mt-2 text-[11px] font-mono text-cyan-300 truncate">
                      Task: {worker.currentTask}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Selected Agent Cognitive Reasoning Loop */}
        <div className="lg:col-span-7 space-y-6">
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs text-emerald-400 font-bold">
                    {currentWorker.role}
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    Isolation: Docker Sandbox Container
                  </span>
                </div>
                <h2 className="text-lg font-bold text-white">
                  {currentWorker.name}
                </h2>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-mono px-3 py-1 rounded bg-slate-950 text-emerald-300 border border-emerald-900/60">
                  Status: {currentWorker.activeStatus}
                </span>
              </div>
            </div>

            {/* Cognitive OODA / ReAct Loop */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Cognitive Reasoning Trace (Observation → Thought → Decision → Action)
                </span>
                <span className="text-[10px] font-mono text-slate-500">Live Agent Scratchpad</span>
              </div>

              <div className="space-y-3">
                {currentWorker.cognitiveStream.map((item, idx) => {
                  const stageColor =
                    item.stage === "OBSERVE"
                      ? "text-cyan-400 bg-cyan-950/80 border-cyan-800/60"
                      : item.stage === "ORIENT"
                      ? "text-indigo-400 bg-indigo-950/80 border-indigo-800/60"
                      : item.stage === "DECIDE"
                      ? "text-amber-400 bg-amber-950/80 border-amber-800/60"
                      : item.stage === "ACT"
                      ? "text-emerald-400 bg-emerald-950/80 border-emerald-800/60"
                      : "text-purple-400 bg-purple-950/80 border-purple-800/60";

                  return (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${stageColor}`}>
                          {item.stage}
                        </span>
                        <span className="text-[11px] font-mono text-slate-500">{item.timestamp}</span>
                      </div>
                      <p className="text-xs text-slate-200 leading-relaxed font-sans">{item.content}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Guardrail Policy Enforcement */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-emerald-400" />
                <span>Enforced Sandbox Boundaries</span>
              </div>
              <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
                <li>Network egress restricted exclusively to whitelisted internal endpoints</li>
                <li>Write permissions confined strictly to designated workspace scratch directory</li>
                <li>Mandatory human sign-off preview generation for any code modification or spend</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
