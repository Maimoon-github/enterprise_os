"use client";

import { organizationClient } from "better-auth/client/plugins";
import { createAuthClient } from "better-auth/react";
import { ac, roles } from "./permissions";

/**
 * The browser side of Better Auth: sign-in/up/out, the active organization,
 * invitations and teams. Same origin as the app, so no baseURL is needed.
 */
export const authClient = createAuthClient({
  plugins: [organizationClient({ ac, roles, teams: { enabled: true } })],
});

export const { signIn, signUp, signOut, useSession, useActiveOrganization, useListOrganizations, organization } =
  authClient;
