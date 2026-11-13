import "server-only";

import { and, eq, gt, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { invitations, members, organizations, users } from "./schema";

/**
 * Who may create an account and an organization on this instance.
 *
 * AUTH_SIGNUP=invite-only (default): the very first account can always be
 * created (it is the operator setting the instance up); after that an
 * account can only be created for an email address with a pending
 * invitation, and only the first organization's owners and admins (or the
 * first user, before any organization exists) can create organizations.
 *
 * AUTH_SIGNUP=open: anyone who can reach the instance can sign up and create
 * organizations — the model for a public, multi-customer deployment. It has
 * to be asked for: an instance is closed unless its operator opens it.
 *
 * Invitations work in both modes.
 */
export type SignupMode = "open" | "invite-only";

export function signupMode(): SignupMode {
  return process.env.AUTH_SIGNUP?.trim().toLowerCase() === "open" ? "open" : "invite-only";
}

/**
 * Whether anyone may sign up without an invitation right now: the instance
 * is open, or it has no account yet. Decides whether "Create one" is offered.
 */
export async function publicSignupAvailable(): Promise<boolean> {
  if (signupMode() === "open") return true;
  const [anyUser] = await db.select({ id: users.id }).from(users).limit(1);
  return !anyUser;
}

/** Whether an account may be created for `email` right now. */
export async function mayCreateAccount(email: string): Promise<boolean> {
  if (signupMode() === "open") return true;
  const [anyUser] = await db.select({ id: users.id }).from(users).limit(1);
  if (!anyUser) return true;
  const [invited] = await db
    .select({ id: invitations.id })
    .from(invitations)
    .where(
      and(
        sql`lower(${invitations.email}) = ${email.toLowerCase()}`,
        eq(invitations.status, "pending"),
        gt(invitations.expiresAt, new Date()),
      ),
    )
    .limit(1);
  return Boolean(invited);
}

/** Whether `userId` may create a new organization. */
export async function mayCreateOrganization(userId: string): Promise<boolean> {
  if (signupMode() === "open") return true;
  const [first] = await db
    .select({ id: organizations.id })
    .from(organizations)
    .orderBy(organizations.createdAt)
    .limit(1);
  if (!first) return true;
  const [membership] = await db
    .select({ role: members.role })
    .from(members)
    .where(and(eq(members.organizationId, first.id), eq(members.userId, userId)))
    .limit(1);
  return Boolean(membership && /\b(owner|admin)\b/.test(membership.role));
}
