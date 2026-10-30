"use client";

import { useState } from "react";

export function ResumeDialog({
  isOpen,
  onClose,
  onResume,
}: {
  isOpen: boolean;
  onClose: () => void;
  onResume: (notes: string) => void;
}) {
  const [notes, setNotes] = useState("");

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full space-y-4">
        <h3 className="text-base font-semibold text-white">Resume Execution Decision</h3>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Enter revision notes or approval context..."
          className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-white"
        />
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-slate-400">Cancel</button>
          <button onClick={() => onResume(notes)} className="px-3 py-1.5 bg-indigo-600 text-xs text-white rounded">Submit</button>
        </div>
      </div>
    </div>
  );
}
