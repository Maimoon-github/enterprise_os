function RowSkeleton() {
  return (
    <tr className="border-b border-stroke-soft-200 animate-pulse">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-bg-soft-200 shrink-0" />
          <div className="space-y-1.5">
            <div className="h-3.5 w-36 rounded bg-bg-soft-200" />
            <div className="h-3 w-52 rounded bg-bg-weak-50" />
          </div>
        </div>
      </td>
      <td className="px-4 py-3"><div className="h-3.5 w-24 rounded bg-bg-soft-200" /></td>
      <td className="px-4 py-3"><div className="h-5 w-20 rounded-full bg-bg-soft-200" /></td>
      <td className="px-4 py-3"><div className="h-3.5 w-20 rounded bg-bg-weak-50" /></td>
      <td className="px-2 py-3"><div className="h-6 w-6 rounded bg-bg-weak-50" /></td>
    </tr>
  );
}

export default function LeadsLoading() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-6 animate-pulse">
        <div className="h-9 w-24 rounded-lg bg-bg-weak-50" />
        <div className="h-9 flex-1 rounded-lg bg-bg-weak-50" />
        <div className="h-9 w-36 rounded-lg bg-bg-weak-50" />
      </div>
      <div className="rounded-xl border border-stroke-soft-200 bg-bg-white-0 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-stroke-soft-200 bg-bg-weak-50 text-left">
              <th className="px-4 py-3 font-semibold text-text-sub-600">Lead</th>
              <th className="px-4 py-3 font-semibold text-text-sub-600">Campaign</th>
              <th className="px-4 py-3 font-semibold text-text-sub-600">Status</th>
              <th className="px-4 py-3 font-semibold text-text-sub-600">Account</th>
              <th className="px-4 py-3 w-10" />
            </tr>
          </thead>
          <tbody>{Array.from({ length: 8 }).map((_, i) => <RowSkeleton key={i} />)}</tbody>
        </table>
      </div>
    </div>
  );
}
