import UnsubscribeClient from "@/components/outreach/UnsubscribeClient";

export const dynamic = "force-dynamic";

export default async function UnsubscribePage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-weak-50 px-4">
      <div className="w-full max-w-sm bg-bg-white-0 border border-stroke-soft-200 rounded-2xl shadow-sm p-8">
        <UnsubscribeClient token={token ?? null} />
      </div>
    </div>
  );
}
