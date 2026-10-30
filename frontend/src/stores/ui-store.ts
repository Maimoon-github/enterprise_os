import { create } from "zustand";
import { clearStoredSession, getStoredSession, UserSession } from "@/types/api";

interface UIStore {
  activeBrandSlug: string;
  isSidebarOpen: boolean;
  userSession: UserSession | null;
  setActiveBrandSlug: (slug: string) => void;
  toggleSidebar: () => void;
  setUserSession: (session: UserSession | null) => void;
  logout: () => void;
}

export const useUIStore = create<UIStore>((set) => ({
  activeBrandSlug: "apex-horizon",
  isSidebarOpen: true,
  userSession: typeof window !== "undefined" ? getStoredSession() : null,
  setActiveBrandSlug: (slug) => set({ activeBrandSlug: slug }),
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  setUserSession: (session) => set({ userSession: session }),
  logout: () => {
    clearStoredSession();
    set({ userSession: null });
  },
}));
