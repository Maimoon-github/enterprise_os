"use client";

import { useState } from "react";

export function CampaignForm({ onSubmit }: { onSubmit: (data: any) => void }) {
  const [name, setName] = useState("");
  const [objective, setObjective] = useState("");

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ name, objective });
      }}
      className="space-y-4"
    >
      <div>
        <label className="block text-xs uppercase font-semibold text-slate-400 mb-1">Title</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white"
        />
      </div>
      <div>
        <label className="block text-xs uppercase font-semibold text-slate-400 mb-1">Objective</label>
        <textarea
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white"
        />
      </div>
      <button type="submit" className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm">
        Synthesize Blueprint
      </button>
    </form>
  );
}
