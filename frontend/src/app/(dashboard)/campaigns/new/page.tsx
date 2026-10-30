"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function NewCampaignPage() {
  const [name, setName] = useState("");
  const [objective, setObjective] = useState("");
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    router.push("/campaigns");
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Synthesize New Campaign Blueprint</h1>
        <p className="text-slate-400 text-sm">Define target objective. The LangGraph supervisor will coordinate research and creative subgraphs.</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <div>
          <label className="block text-xs uppercase font-semibold text-slate-400 mb-1">Campaign Title</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Q4 Multi-Platform Product Launch"
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
          />
        </div>
        <div>
          <label className="block text-xs uppercase font-semibold text-slate-400 mb-1">Strategic Objective & Directives</label>
          <textarea
            rows={4}
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            placeholder="Describe positioning, target audience segments, and core conversions..."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
          />
        </div>
        <button
          type="submit"
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition"
        >
          Initialize LangGraph Execution
        </button>
      </form>
    </div>
  );
}
