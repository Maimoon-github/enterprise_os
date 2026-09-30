"use client";

import React, { useState } from "react";
import {
  Bot,
  Box,
  ExternalLink,
  Play,
} from "lucide-react";
import { MOCK_WORKER_ROSTER } from "@/lib/api";
import { WorkerRole } from "@/lib/types";
import { getStoredSettings, EnterpriseSettings } from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

export default function WorkersPage() {
  const [roster, setRoster] = useState(MOCK_WORKER_ROSTER);
  const [selectedRole, setSelectedRole] = useState<WorkerRole>("W_DEV");
  const [settings] = useState<EnterpriseSettings>(getStoredSettings());
  const { addToast } = useToast();

  const currentWorker = roster.find((w) => w.role === selectedRole) || roster[0];

  const handleTriggerOodaStep = () => {
    const stages: ("OBSERVE" | "ORIENT" | "DECIDE" | "ACT" | "REFLECT")[] = [
      "OBSERVE",
      "ORIENT",
      "DECIDE",
      "ACT",
      "REFLECT",
    ];
    const randomStage = stages[Math.floor(Math.random() * stages.length)];
    const messages = {
      OBSERVE: "Queried isolated sandbox file virtualization tree; identified AST structure.",
      ORIENT: "Evaluating WCAG 2.1 AA accessibility contrast rules against design token palette.",
      DECIDE: "Formulating AST transform plan to inject aria-label and keyboard event listeners.",
      ACT: "Executed sandboxed test harness with Jest; 12/12 assertions passed in 140ms.",
      REFLECT: "Verified zero policy violations. Output envelope ready for evidence synthesis.",
    };

    const newThought = {
      stage: randomStage,
      content: messages[randomStage],
      timestamp: new Date().toLocaleTimeString(),
    };

    setRoster((prev) =>
      prev.map((worker) => {
        if (worker.role === selectedRole) {
          return {
            ...worker,
            activeStatus: "executing",
            cognitiveStream: [newThought, ...worker.cognitiveStream],
          };
        }
        return worker;
      })
    );

    addToast({
      type: "info",
      title: `${selectedRole} Cognitive Step (${randomStage})`,
      message: newThought.content,
    });
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Bot className="w-6 h-6 text-emerald-400" />
            <span>7 Bounded Worker Engines & Cognitive Stream</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Zero-trust agent sandbox boundaries. Each bounded agent operates under explicit prompt restrictions and immutable role policies.
          </p>
        </div>

        {/* Sandbox Website Direct Link */}
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
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
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
                <button
                  onClick={handleTriggerOodaStep}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-emerald-600/20 transition-all"
                >
                  <Play className="w-3 h-3 fill-white" />
                  <span>1-Click OODA Step</span>
                </button>
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
                      className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 text-xs font-mono"
                    >
                      <div className="flex items-center justify-between">
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${stageColor}`}
                        >
                          {item.stage}
                        </span>
                        <span className="text-slate-500 text-[10px]">{item.timestamp}</span>
                      </div>
                      <p className="text-slate-300 font-sans leading-relaxed">{item.content}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
