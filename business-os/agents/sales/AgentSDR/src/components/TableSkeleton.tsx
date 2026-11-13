export default function TableSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="h-4 w-48 bg-bg-weak-50 rounded animate-pulse" />

      <div className="overflow-hidden rounded-xl border border-stroke-soft-200 shadow-sm bg-bg-white-0">
        <table className="min-w-full">
          <thead>
            <tr className="bg-bg-weak-50 border-b border-stroke-soft-200">
              {[24, 140, 140, 100, 60, 100, 100, 60, 80, 70, 70, 120, 70].map((w, i) => (
                <th key={i} className="px-4 py-3">
                  <div className="h-3 bg-bg-soft-200 rounded animate-pulse" style={{ width: w }} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-stroke-soft-200">
            {Array.from({ length: 20 }).map((_, rowIdx) => (
              <tr key={rowIdx}>
                {[24, 140, 140, 90, 40, 80, 80, 50, 70, 50, 50, 100, 60].map((w, colIdx) => (
                  <td key={colIdx} className="px-4 py-3">
                    <div
                      className="h-4 bg-bg-weak-50 rounded animate-pulse"
                      style={{
                        width: w,
                        animationDelay: `${(rowIdx * 13 + colIdx * 7) % 300}ms`,
                      }}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <div className="h-9 w-24 bg-bg-weak-50 rounded-lg animate-pulse" />
        <div className="flex gap-1">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-9 w-9 bg-bg-weak-50 rounded-lg animate-pulse" style={{ animationDelay: `${i * 40}ms` }} />
          ))}
        </div>
        <div className="h-9 w-16 bg-bg-weak-50 rounded-lg animate-pulse" />
      </div>
    </div>
  );
}
