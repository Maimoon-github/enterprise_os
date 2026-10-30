export default function SkillsPage() {
  const skills = [
    { name: "brand-voice-audit", path: "skills/brand-voice-audit/SKILL.md", tier: "Tier 1/2/3", status: "validated" },
    { name: "multi-platform-copy", path: "skills/multi-platform-copy/SKILL.md", tier: "Tier 1/2/3", status: "validated" },
    { name: "competitor-recon", path: "skills/competitor-recon/SKILL.md", tier: "Tier 1/2/3", status: "validated" },
    { name: "media-compliance", path: "skills/media-compliance/SKILL.md", tier: "Tier 1/2/3", status: "validated" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Agent Skills (SKILL.md Packages)</h1>
        <p className="text-slate-400 text-sm">Progressive-disclosure domain playbooks validated against the Agent Skills Specification.</p>
      </div>

      <div className="space-y-3">
        {skills.map((s) => (
          <div key={s.name} className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-white font-mono text-sm">{s.name}</h3>
              <p className="text-xs text-slate-400 font-mono mt-1">{s.path}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-400 bg-slate-950 px-2 py-1 rounded border border-slate-800">{s.tier}</span>
              <span className="text-xs text-emerald-400 font-semibold">{s.status}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
