"use client";

import { useCallback, useEffect, useState } from "react";
import { authClient, useSession } from "@/lib/auth/client";
import { roles, type OrgRole } from "@/lib/auth/permissions";

// Written out rather than inferred: the client's inferred type is too deep for tsc to resolve here.
export type OrgMember = {
  id: string;
  userId: string;
  role: string;
  createdAt: Date | string;
  user: { name: string; email: string };
};
export type OrgInvitation = { id: string; email: string; role: string; status: string; expiresAt: Date | string };
type FullOrg = { id: string; name: string; slug: string; logo?: string | null; members: OrgMember[]; invitations: OrgInvitation[] };

type Permissions = Parameters<typeof authClient.organization.checkRolePermission>[0]["permissions"];

/** The role names we know; anything else (a custom role) is treated as a plain member. */
export function asOrgRole(role: string | undefined): OrgRole {
  return role && role in roles ? (role as OrgRole) : "member";
}

/**
 * The active organization with its members and invitations, plus what the
 * current user's role may do. `can` reads the same role definitions the
 * server enforces (permissions.ts), so a control is hidden exactly when
 * Better Auth would refuse it; the server remains the authority.
 */
export function useOrgAccess() {
  const { data: session } = useSession();
  const [org, setOrg] = useState<FullOrg | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    const res = await authClient.organization.getFullOrganization();
    if (res.error) setError(res.error.message || "Could not load the organization.");
    else {
      setError("");
      setOrg(res.data as unknown as FullOrg | null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    // Initial fetch; state is set after the awaited response, not synchronously.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload();
  }, [reload]);

  const userId = session?.user.id;
  const me = org?.members.find((m) => m.userId === userId);
  const role = me ? asOrgRole(me.role) : undefined;

  const can = useCallback(
    (permissions: Permissions) => (role ? authClient.organization.checkRolePermission({ permissions, role }) : false),
    [role],
  );

  return { org, me, role, userId, loading, error, reload, can };
}

export function useAsyncAction() {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  /** Runs a Better Auth call; resolves true on success, otherwise shows its message inline. */
  async function run(key: string, call: () => Promise<{ error?: { message?: string } | null }>): Promise<boolean> {
    setBusy(key);
    setError("");
    try {
      const res = await call();
      if (res.error) {
        setError(res.error.message || "Something went wrong.");
        return false;
      }
      return true;
    } catch {
      setError("Network error. Try again.");
      return false;
    } finally {
      setBusy(null);
    }
  }
  return { busy, error, setError, run };
}
