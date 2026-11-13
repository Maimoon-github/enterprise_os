import { createAccessControl } from "better-auth/plugins/access";
import { adminAc, defaultStatements, memberAc, ownerAc } from "better-auth/plugins/organization/access";

/**
 * Who may do what inside an organization. Client-safe: the server enforces
 * it (src/lib/auth/context.ts → requirePermission) and the UI reads the same
 * definitions to hide controls a member cannot use.
 *
 * Better Auth's own statements (organization, member, invitation, team, ac)
 * keep their default grants; ours are added on top:
 * - integrations — connect / edit / disconnect Unipile, Google, R2, enrichment keys
 * - aiSettings — the OpenRouter connection and model choices
 */
export const statements = {
  ...defaultStatements,
  integrations: ["manage"],
  aiSettings: ["manage"],
} as const;

export const ac = createAccessControl(statements);

export const owner = ac.newRole({
  ...ownerAc.statements,
  integrations: ["manage"],
  aiSettings: ["manage"],
});

export const admin = ac.newRole({
  ...adminAc.statements,
  integrations: ["manage"],
  aiSettings: ["manage"],
});

export const member = ac.newRole({
  ...memberAc.statements,
});

export const roles = { owner, admin, member };

export type OrgRole = keyof typeof roles;

export const ROLE_LABELS: Record<OrgRole, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
};
