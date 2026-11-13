import { headers } from "next/headers";
import { NextResponse } from "next/server";
import { auth } from "@/lib/auth/server";
import { SetupAlreadyDoneError, createInitialAdmin, needsSetup } from "@/lib/auth/setup";
import { validateSetupInput } from "@/lib/auth/setupInput";

/**
 * First-run setup: creates the first admin and organization, then signs them
 * in. Public in the proxy, so it refuses on its own the moment any user exists.
 */
export async function POST(request: Request) {
  const done = () => NextResponse.json({ error: "This instance is already set up. Sign in instead." }, { status: 409 });
  if (!(await needsSetup())) return done();

  const parsed = validateSetupInput(await request.json().catch(() => null));
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });

  try {
    // The organization and membership exist before the session does, so the
    // session's activeOrganizationId hook finds them.
    await createInitialAdmin(parsed.value);
  } catch (error) {
    if (error instanceof SetupAlreadyDoneError) return done();
    console.error("[setup] could not create the first account:", error);
    return NextResponse.json({ error: "Could not create the account. Check the server logs." }, { status: 500 });
  }

  try {
    // nextCookies() sets the session cookie on this response.
    await auth.api.signInEmail({ body: { email: parsed.value.email, password: parsed.value.password }, headers: await headers() });
  } catch (error) {
    console.error("[setup] account created but sign-in failed:", error);
    return NextResponse.json({ ok: true, signedIn: false });
  }
  return NextResponse.json({ ok: true, signedIn: true });
}
