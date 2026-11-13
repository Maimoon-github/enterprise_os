import { redirect } from "next/navigation";
import { needsSetup } from "@/lib/auth/setup";
import { SetupForm } from "./SetupForm";

// Reads the database on every request: it must go dead the moment a user exists.
export const dynamic = "force-dynamic";

export default async function SetupPage() {
  if (!(await needsSetup())) redirect("/sign-in");
  return <SetupForm />;
}
