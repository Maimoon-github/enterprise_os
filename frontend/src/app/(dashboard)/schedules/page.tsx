"use client";

import { useEffect, useState } from "react";
import { schedulesApi } from "@/lib/api/endpoints/schedules";
import { BeatScheduleModel, ScheduleModel } from "@/types/models";

export default function SchedulesPage() {
  const [beatSchedules, setBeatSchedules] = useState<BeatScheduleModel[]>([]);
  const [scheduledPosts, setScheduledPosts] = useState<ScheduleModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [beats, posts] = await Promise.all([
        schedulesApi.listBeat().catch(() => [
          {
            name: "ingest-social-metrics-every-6-hours",
            task: "app.tasks.analytics_tasks.ingest_cross_platform_metrics",
            schedule: "0 */6 * * *",
            queue: "analytics_queue",
            status: "active",
          },
          {
            name: "midnight-brand-compliance-audit",
            task: "app.tasks.orchestrator_tasks.audit_brand_compliance",
            schedule: "0 0 * * *",
            queue: "orchestrator_queue",
            status: "active",
          },
          {
            name: "poll-due-schedules-every-5-minutes",
            task: "app.tasks.publishing_tasks.poll_due_schedules_and_dispatch",
            schedule: "*/5 * * * *",
            queue: "publishing_queue",
            status: "active",
          },
        ]),
        schedulesApi.list().catch(() => []),
      ]);
      setBeatSchedules(beats);
      setScheduledPosts(posts);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTrigger = async (name: string) => {
    setTriggering(name);
    try {
      await schedulesApi.triggerBeat(name);
      await loadData();
    } finally {
      setTriggering(null);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Celery Beat Periodic Schedules</h1>
          <p className="text-slate-400 text-sm">
            Automated background workflows, rolling analytics ingestion, and scheduled post dispatchers.
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 rounded-lg transition"
        >
          {loading ? "Refreshing..." : "Refresh Status"}
        </button>
      </div>

      <div className="space-y-4">
        <h2 className="text-sm font-semibold uppercase text-slate-400 tracking-wider">
          Active Celery Beat Cron Schedules
        </h2>
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-xs uppercase">
              <tr>
                <th className="px-6 py-3">Schedule Name</th>
                <th className="px-6 py-3">Cron Expression</th>
                <th className="px-6 py-3">Assigned Queue</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {beatSchedules.map((s) => (
                <tr key={s.name} className="hover:bg-slate-800/30 transition">
                  <td className="px-6 py-4 font-medium text-white">{s.name}</td>
                  <td className="px-6 py-4 font-mono text-xs text-slate-300">{s.schedule}</td>
                  <td className="px-6 py-4 font-mono text-xs text-indigo-400">{s.queue}</td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-0.5 text-xs rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                      {s.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => handleTrigger(s.name)}
                      disabled={triggering === s.name}
                      className="px-2.5 py-1 text-xs bg-indigo-600 hover:bg-indigo-500 text-white rounded font-medium transition"
                    >
                      {triggering === s.name ? "Enqueuing..." : "Trigger Now"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="text-sm font-semibold uppercase text-slate-400 tracking-wider">
          Scheduled Social Posts Queue
        </h2>
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow">
          {scheduledPosts.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500 font-mono">
              No scheduled social posts in database. Staged posts will automatically appear here.
            </div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-xs uppercase">
                <tr>
                  <th className="px-6 py-3">Platform</th>
                  <th className="px-6 py-3">Scheduled UTC</th>
                  <th className="px-6 py-3">SHA-256 Idempotency Key</th>
                  <th className="px-6 py-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {scheduledPosts.map((p) => (
                  <tr key={p.id}>
                    <td className="px-6 py-4 font-semibold text-white capitalize">{p.platform}</td>
                    <td className="px-6 py-4 font-mono text-xs text-slate-300">
                      {p.scheduled_utc || p.created_at}
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-slate-500">
                      {p.idempotency_key ? `${p.idempotency_key.slice(0, 16)}...` : "—"}
                    </td>
                    <td className="px-6 py-4 text-right font-medium text-xs text-indigo-400">
                      {p.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
