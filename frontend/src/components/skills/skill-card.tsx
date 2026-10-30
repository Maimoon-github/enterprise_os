export function SkillCard({ skill }: { skill: any }) {
  return (
    <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
      <div className="text-sm font-mono font-bold text-white">{skill.name}</div>
      <div className="text-xs text-slate-400">{skill.description}</div>
    </div>
  );
}
