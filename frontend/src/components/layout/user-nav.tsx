"use client";

import { useRouter } from "next/navigation";
import { useUIStore } from "@/stores/ui-store";

export function UserNav() {
  const router = useRouter();
  const session = useUIStore((s) => s.userSession);
  const logout = useUIStore((s) => s.logout);

  const handleSignOut = () => {
    logout();
    router.push("/login");
  };

  const email = session?.email || "admin@marketing-os.local";
  const role = session?.role || "admin";

  return (
    <div className="flex items-center gap-3 text-xs">
      <div className="flex flex-col items-end">
        <span className="font-semibold text-white">{session?.full_name || email.split("@")[0]}</span>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
            {role}
          </span>
          <span className="text-slate-500 hidden sm:inline">({email})</span>
        </div>
      </div>
      <button
        onClick={handleSignOut}
        title="Sign Out"
        className="px-2 py-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition text-xs"
      >
        Sign Out
      </button>
    </div>
  );
}
