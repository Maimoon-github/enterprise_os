import { create } from "zustand";

interface UIStore {
  activeBrandSlug: string;
  isSidebarOpen: boolean;
  setActiveBrandSlug: (slug: string) => void;
  toggleSidebar: () => void;
}

export const useUIStore = create<UIStore>((set) => ({
  activeBrandSlug: "apex-horizon",
  isSidebarOpen: true,
  setActiveBrandSlug: (slug) => set({ activeBrandSlug: slug }),
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
}));
