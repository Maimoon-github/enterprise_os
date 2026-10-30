import { UserNav } from "./user-nav";

export function Header() {
  return (
    <header className="h-16 border-b border-glass-subtle bg-glass-base backdrop-blur-glass px-8 flex items-center justify-between">
      <div className="text-sm font-semibold text-bloodstone-text">Brand Control Plane</div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-bloodstone-mint shadow-[0_0_8px_#7bf0a7] animate-pulse"></span>
          <span className="text-xs text-bloodstone-text-muted">FastAPI & LangGraph Connected</span>
        </div>
        <UserNav />
      </div>
    </header>
  );
}
