export function SkillEditor({ content }: { content: string }) {
  return (
    <textarea
      defaultValue={content}
      rows={12}
      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-300"
    />
  );
}
