export function Header() {
  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/50 backdrop-blur px-8 flex items-center justify-between">
      <div className="text-sm font-semibold text-slate-300">Brand Control Plane</div>
      <div className="flex items-center gap-4">
        <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
        <span className="text-xs text-slate-400">Ollama Connected</span>
      </div>
    </header>
  );
}
