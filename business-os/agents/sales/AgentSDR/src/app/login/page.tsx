import { redirect } from "next/navigation";

/** The shared-password page is gone; old bookmarks land on the new sign-in. */
export default async function LoginPage({ searchParams }: { searchParams: Promise<{ from?: string }> }) {
  const { from } = await searchParams;
  redirect(from ? `/sign-in?from=${encodeURIComponent(from)}` : "/sign-in");
}
