export * from "@marketing-os/contracts";
import { apiClient } from "@/lib/api/client";

export interface UserSession {
  id: string;
  email: string;
  role: "admin" | "editor" | "operator" | "viewer" | string;
  full_name?: string | null;
  accessToken?: string;
  refreshToken?: string;
}

export const apiFetch = apiClient;

export function hasRole(
  userRole: string,
  minRole: "admin" | "editor" | "operator" | "viewer"
): boolean {
  const levels: Record<string, number> = {
    admin: 4,
    editor: 3,
    operator: 2,
    viewer: 1,
  };
  return (levels[userRole] || 1) >= (levels[minRole] || 1);
}

export function getStoredSession(): UserSession | null {
  if (typeof window === "undefined") return null;
  const user = localStorage.getItem("user");
  return user ? JSON.parse(user) : null;
}

export function setStoredSession(session: UserSession): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("user", JSON.stringify(session));
    if (session.accessToken) {
      localStorage.setItem("token", session.accessToken);
    }
    if (session.refreshToken) {
      localStorage.setItem("refreshToken", session.refreshToken);
    }
  }
}

export function clearStoredSession(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("user");
    localStorage.removeItem("token");
    localStorage.removeItem("refreshToken");
  }
}
