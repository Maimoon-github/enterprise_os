"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

interface AgentItem {
  name: string;
  model: string;
  role: string;
  queue: string;
}

export default function AgentsFleetPage() {
  const [agents, setAgents] = useState<AgentItem[]>([
    {
      name: "Master Orchestrator (Supervisor)",
      model: "ollama:llama3.3:70b",
      role: "Routing, State & Approval Governance",
      queue: "orchestrator_queue",
    },
    {
      name: "Research & Recon Specialist",
      model: "ollama:qwen2.5:14b",
      role: "Market Intelligence, Competitor Analysis",
      queue: "orchestrator_queue",
    },
    {
      name: "Creative Blueprint Architect",
      model: "ollama:llama3.3:70b",
      role: "Copy Synthesis, Voice Consistency",
      queue: "orchestrator_queue",
    },
    {
      name: "Platform Fan-Out Publisher",
      model: "ollama:qwen2.5:14b",
      role: "Map-Reduce Publishing to 8 Channels",
      queue: "publishing_queue",
    },
    {
      name: "Closed-Loop Analytics Judge",
      model: "ollama:qwen2.5:14b",
      role: "ReWOO Metric Anomaly Detection",
      queue: "analytics_queue",
    },
  ]);

  const queues = [
    { name: "orchestrator_queue", concurrency: 4, tasks: "Graph Steps & HITL Resumes", speed: "High" },
    { name: "publishing_queue", concurrency: 8, tasks: "Multi-Platform Fan-Out", speed: "Normal" },
    { name: "media_queue", concurrency: 2, tasks: "Video Transcoding & MinIO Ingestion", speed: "Compute" },
    { name: "analytics_queue", concurrency: 2, tasks: "Polars Z-Score Rolling Windows", speed: "Batch" },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Agent Fleet & Worker Infrastructure</h1>
        <p className="text-slate-400 text-sm">
          Inspect local Ollama model assignments, tool scopes, and Celery worker queue concurrency.
        </p>
      </div>

      <div className="space-y-4">
        <h2 className="text-sm font-semibold uppercase text-slate-400 tracking-wider">
          Asynchronous Worker Queue Status
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {queues.map((q) => (
            <div key={q.name} className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-semibold text-indigo-400">{q.name}</span>
                <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                  Concurrency: {q.concurrency}
                </span>
              </div>
              <p className="text-xs text-slate-300">{q.tasks}</p>
              <div className="text-[10px] text-slate-500 font-mono">Routing Profile: {q.speed} Priority</div>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="text-sm font-semibold uppercase text-slate-400 tracking-wider">
          Supervised Agent Fleet
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agents.map((agent) => (
            <div key={agent.name} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-white text-sm">{agent.name}</h3>
                <span className="text-xs font-mono bg-slate-950 px-2 py-0.5 rounded text-indigo-400 border border-slate-800">
                  {agent.model}
                </span>
              </div>
              <p className="text-xs text-slate-400">{agent.role}</p>
              <div className="text-[10px] font-mono text-slate-500">
                Assigned Queue: <span className="text-slate-400">{agent.queue}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
