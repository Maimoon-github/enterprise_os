export * from "@marketing-os/contracts";

export interface UserSession {
  id: string;
  email: string;
  role: "admin" | "strategist" | "approver" | "viewer";
}
