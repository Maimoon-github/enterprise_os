"use client";

import { useEffect, useState } from "react";
import { skillsApi } from "@/lib/api/endpoints/skills";

export function SkillEditor({
  skillName,
  initialContent,
  onValidated,
}: {
  skillName?: string;
  initialContent?: string;
  content?: string;
  onValidated?: (res: any) => void;
}) {
  const [text, setText] = useState(initialContent || "");
  const [validating, setValidating] = useState(false);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    setText(initialContent || "");
  }, [initialContent]);

  const handleValidate = async () => {
    setValidating(true);
    try {
      const res = await skillsApi.validate({
        name: skillName || "skill-preview",
        content: text,
      });
      setResult(res);
      onValidated?.(res);
    } catch (err: any) {
      setResult({
        valid: false,
        errors: [err.message || "Validation failed"],
      });
    } finally {
      setValidating(false);
    }
  };

  return (
    <div className="space-y-4 bg-slate-900 border border-slate-800 rounded-xl p-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-white text-sm font-mono">
            {skillName || "Custom Skill"} / SKILL.md
          </h3>
          <p className="text-xs text-slate-400">
            Tier 2 Instructions (<span className="text-slate-300">&lt;500 lines, &lt;5,000 tokens</span>)
          </p>
        </div>
        <button
          onClick={handleValidate}
          disabled={validating}
          className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition"
        >
          {validating ? "Validating..." : "Validate Spec (CI Checker)"}
        </button>
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={14}
        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
      />

      {result && (
        <div
          className={`p-3 rounded-lg border text-xs ${
            result.valid
              ? "bg-emerald-950/40 border-emerald-800 text-emerald-300"
              : "bg-rose-950/40 border-rose-800 text-rose-300"
          }`}
        >
          <div className="font-semibold flex items-center gap-2">
            <span>{result.valid ? "✅ Spec Validated" : "❌ Spec Violations Found"}</span>
            {result.token_estimate !== undefined && (
              <span className="font-mono text-[11px] text-slate-300">
                (Tokens: ~{result.token_estimate}, Lines: {result.lines_count || text.split("\n").length})
              </span>
            )}
          </div>
          {result.errors && result.errors.length > 0 && (
            <ul className="mt-1 list-disc list-inside space-y-0.5">
              {result.errors.map((e: string, i: number) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
