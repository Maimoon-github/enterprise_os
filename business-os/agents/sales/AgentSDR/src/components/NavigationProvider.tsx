"use client";

import { createContext, useContext, useTransition, useCallback } from "react";
import { useRouter } from "next/navigation";

type NavCtx = {
  isPending: boolean;
  navigate: (url: string) => void;
};

const NavContext = createContext<NavCtx>({
  isPending: false,
  navigate: () => {},
});

export function NavigationProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const navigate = useCallback(
    (url: string) => startTransition(() => router.push(url)),
    [router]
  );

  return (
    <NavContext.Provider value={{ isPending, navigate }}>
      {children}
    </NavContext.Provider>
  );
}

export function useNavigation() {
  return useContext(NavContext);
}
