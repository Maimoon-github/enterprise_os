import { toNextJsHandler } from "better-auth/next-js";
import { auth } from "@/lib/auth/server";

// Better Auth's endpoints: /api/auth/sign-in/*, /sign-up/*, /sign-out,
// /get-session, /organization/*, /callback/google, … (public in proxy.ts).
export const { GET, POST } = toNextJsHandler(auth);
