export function SkillCard({
  skill,
  onSelect,
  isSelected,
}: {
  skill: any;
  onSelect?: (skill: any) => void;
  isSelected?: boolean;
}) {
  return (
    <div
      onClick={() => onSelect?.(skill)}
      className={`p-5 bg-slate-900 border rounded-xl space-y-3 cursor-pointer transition ${
        isSelected
          ? "border-indigo-500 shadow-lg shadow-indigo-500/10"
          : "border-slate-800 hover:border-slate-700"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="text-sm font-mono font-bold text-white flex items-center gap-2">
          <span>{skill.name}</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">
            {skill.tier || "Tier 1/2/3"}
          </span>
        </div>
        <span className="text-xs px-2 py-0.5 rounded font-medium bg-emerald-950/60 border border-emerald-800 text-emerald-400">
          {skill.valid ? "Validated" : "Error"}
        </span>
      </div>

      <p className="text-xs text-slate-300 leading-relaxed">{skill.description}</p>

      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 pt-2 border-t border-slate-800">
        <div>
          Tokens: <span className="text-white font-mono">{skill.token_estimate || "~350"}</span>
        </div>
        <div>
          Lines: <span className="text-white font-mono">{skill.lines_count || "28"}</span>
        </div>
        {skill.allowed_tools && skill.allowed_tools.length > 0 && (
          <div className="flex items-center gap-1">
            Tools: <span className="text-indigo-400 font-mono">{skill.allowed_tools.length}</span>
          </div>
        )}
      </div>

      {skill.tier3_resources && skill.tier3_resources.length > 0 && (
        <div className="text-[11px] font-mono text-slate-400 bg-slate-950/70 p-2 rounded border border-slate-800/80">
          Tier 3: {skill.tier3_resources.join(", ")}
        </div>
      )}
    </div>
  );
}
