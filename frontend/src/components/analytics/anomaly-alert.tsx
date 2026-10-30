export function AnomalyAlert({ anomaly }: { anomaly: any }) {
  return (
    <div className="p-4 bg-amber-950/30 border border-amber-800/60 rounded-xl text-xs text-amber-300">
      <div className="font-bold">Anomaly Alert: {anomaly.platform}</div>
      <p className="mt-1 text-slate-300">{anomaly.recommendation}</p>
    </div>
  );
}
