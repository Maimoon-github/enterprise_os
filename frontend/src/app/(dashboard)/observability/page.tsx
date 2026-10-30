"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

interface EvaluationItem {
  trace_id: string;
  name: string;
  score: number;
  label?: string | null;
  annotator_kind: string;
  comment?: string | null;
  created_at?: string | null;
}

interface ObservabilityStats {
  trajectory_gate_pass_rate: number;
  brand_voice_rubric_avg: number;
  token_velocity_per_min: number;
}

interface GoldenRegressionResult {
  total_scenarios: number;
  passed: number;
  failed: number;
  pass_rate: number;
  results: Array<{
    scenario_id: string;
    description: string;
    passed: boolean;
    layer1_passed: boolean;
    layer2_passed: boolean;
    layer3_passed: boolean;
    scores: Record<string, number>;
  }>;
}

export default function ObservabilityPage() {
  const [stats, setStats] = useState<ObservabilityStats>({
    trajectory_gate_pass_rate: 0.98,
    brand_voice_rubric_avg: 0.92,
    token_velocity_per_min: 450,
  });
  const [evaluations, setEvaluations] = useState<EvaluationItem[]>([]);
  const [regressionResult, setRegressionResult] = useState<GoldenRegressionResult | null>(null);
  const [isRunningRegression, setIsRunningRegression] = useState(false);

  useEffect(() => {
    apiClient<ObservabilityStats>("/observability/stats")
      .then((data) => {
        if (data) setStats(data);
      })
      .catch(() => {});

    apiClient<{ evaluations: EvaluationItem[] }>("/observability/evaluations")
      .then((data) => {
        if (data?.evaluations) setEvaluations(data.evaluations);
      })
      .catch(() => {});
  }, []);

  const handleRunRegression = async () => {
    setIsRunningRegression(true);
    try {
      const res = await apiClient<GoldenRegressionResult>("/observability/evaluations/run", {
        method: "POST",
      });
      setRegressionResult(res);
      // Refresh evaluations list after running regression
      const updated = await apiClient<{ evaluations: EvaluationItem[] }>("/observability/evaluations");
      if (updated?.evaluations) setEvaluations(updated.evaluations);
    } catch (err) {
      console.error("Failed to run golden regression suite:", err);
    } finally {
      setIsRunningRegression(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Observability & Evaluations</h1>
          <p className="text-slate-400 text-sm">OpenTelemetry distributed traces exported to self-hosted Langfuse.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleRunRegression}
            disabled={isRunningRegression}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
          >
            {isRunningRegression ? "Running Regression..." : "Run Golden Regression Suite"}
          </button>
          <a
            href="http://localhost:3001"
            target="_blank"
            rel="noreferrer"
            className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
          >
            Open Langfuse Console ↗
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs uppercase font-semibold text-slate-400">Semantic Conventions</span>
          <p className="text-base font-semibold mt-2 text-white">OpenInference Span Kinds</p>
          <p className="text-xs text-slate-500 mt-1">AGENT, CHAIN, LLM, TOOL, RETRIEVER</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs uppercase font-semibold text-slate-400">Trajectory Gate</span>
          <p className="text-base font-semibold mt-2 text-emerald-400">
            {(stats.trajectory_gate_pass_rate * 100).toFixed(0)}% Valid Order
          </p>
          <p className="text-xs text-slate-500 mt-1">Retrieval ≺ Draft ≺ Approval</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs uppercase font-semibold text-slate-400">Brand Voice Rubric</span>
          <p className="text-base font-semibold mt-2 text-emerald-400">
            {stats.brand_voice_rubric_avg.toFixed(2)} Average Score
          </p>
          <p className="text-xs text-slate-500 mt-1">Evaluated by isolated LLM judge</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <span className="text-xs uppercase font-semibold text-slate-400">Token Velocity</span>
          <p className="text-base font-semibold mt-2 text-indigo-400">
            {stats.token_velocity_per_min} tokens/min
          </p>
          <p className="text-xs text-slate-500 mt-1">Real-time throughput</p>
        </div>
      </div>

      {regressionResult && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Golden Suite Regression Results</h2>
            <span
              className={`px-3 py-1 rounded-full text-xs font-semibold ${
                regressionResult.pass_rate >= 0.8
                  ? "bg-emerald-900/50 text-emerald-400 border border-emerald-700/50"
                  : "bg-red-900/50 text-red-400 border border-red-700/50"
              }`}
            >
              Pass Rate: {(regressionResult.pass_rate * 100).toFixed(1)}% ({regressionResult.passed}/{regressionResult.total_scenarios})
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {regressionResult.results.map((r) => (
              <div
                key={r.scenario_id}
                className="bg-slate-950 border border-slate-800 rounded-lg p-3 space-y-2 text-xs"
              >
                <div className="flex items-center justify-between font-mono font-medium text-slate-300">
                  <span>{r.scenario_id}</span>
                  <span className={r.passed ? "text-emerald-400" : "text-rose-400"}>
                    {r.passed ? "PASSED" : "FAILED"}
                  </span>
                </div>
                <p className="text-slate-400">{r.description}</p>
                <div className="flex gap-2 text-[10px] text-slate-500 font-mono">
                  <span>L1: {r.layer1_passed ? "✓" : "✗"}</span>
                  <span>L2: {r.layer2_passed ? "✓" : "✗"}</span>
                  <span>L3: {r.layer3_passed ? "✓" : "✗"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <h2 className="text-lg font-semibold text-white">Recent Evaluation Records</h2>
        {evaluations.length === 0 ? (
          <p className="text-slate-500 text-sm">No evaluation records captured yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="border-b border-slate-800 text-slate-400 uppercase font-mono">
                <tr>
                  <th className="py-2.5 px-3">Trace ID</th>
                  <th className="py-2.5 px-3">Evaluation Metric</th>
                  <th className="py-2.5 px-3">Kind</th>
                  <th className="py-2.5 px-3">Score</th>
                  <th className="py-2.5 px-3">Label</th>
                  <th className="py-2.5 px-3">Comment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 font-mono">
                {evaluations.map((e, idx) => (
                  <tr key={`${e.trace_id}-${e.name}-${idx}`} className="hover:bg-slate-800/40">
                    <td className="py-2 px-3 text-slate-400">{e.trace_id.slice(0, 12)}...</td>
                    <td className="py-2 px-3 font-medium text-white">{e.name}</td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] ${e.annotator_kind === "LLM" ? "bg-purple-900/40 text-purple-300" : "bg-blue-900/40 text-blue-300"}`}>
                        {e.annotator_kind}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      <span className={e.score >= 0.8 ? "text-emerald-400 font-semibold" : "text-amber-400 font-semibold"}>
                        {typeof e.score === "number" ? e.score.toFixed(2) : e.score}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-400">{e.label || "-"}</td>
                    <td className="py-2 px-3 text-slate-400 truncate max-w-xs">{e.comment || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
