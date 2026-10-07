"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Kanban,
  CheckCircle2,
  RotateCcw,
  ArrowRight,
  Zap,
  Box,
} from "lucide-react";
import Link from "next/link";
import { api, MOCK_TASKS } from "@/lib/api";
import { CanonicalTaskState, TaskStatus } from "@/lib/types";
import { useToast } from "@/components/ui/Toast";

const COLUMNS: { id: TaskStatus; title: string; color: string; borderColor: string }[] = [
  { id: "pending", title: "Pending Clearance", color: "text-slate-400", borderColor: "border-slate-800" },
  { id: "granted", title: "Granted (Sandbox Ready)", color: "text-cyan-400", borderColor: "border-cyan-800/60" },
  { id: "in_progress", title: "In Progress (OODA)", color: "text-indigo-400", borderColor: "border-indigo-800/60" },
  { id: "completed", title: "Completed & Verified", color: "text-emerald-400", borderColor: "border-emerald-800/60" },
  { id: "held", title: "Held / Action Required", color: "text-amber-400", borderColor: "border-amber-800/60" },
];

export default function TasksPage() {
  const [tasks, setTasks] = useState<CanonicalTaskState[]>(MOCK_TASKS);
  const [selectedTask, setSelectedTask] = useState<CanonicalTaskState | null>(null);
  const [selectedDirectiveFilter, setSelectedDirectiveFilter] = useState<string>("ALL");
  const { addToast } = useToast();

  const fetchTasks = useCallback(async () => {
    const data = await api.getTasks(selectedDirectiveFilter === "ALL" ? undefined : selectedDirectiveFilter);
    if (data && data.length > 0) setTasks(data);
  }, [selectedDirectiveFilter]);

  useEffect(() => {
    fetchTasks();
    const timer = setInterval(fetchTasks, 3000);
    return () => clearInterval(timer);
  }, [fetchTasks]);

  const handleAdvanceStatus = async (taskId: string, nextStatus: TaskStatus) => {
    try {
      const updated = await api.advanceTaskStatus(taskId, nextStatus);
      await fetchTasks();
      if (selectedTask?.task_id === taskId) {
        setSelectedTask(updated);
      }
      addToast({
        type: "success",
        title: `Task ${taskId} → ${nextStatus.toUpperCase()}`,
        message: `Version v${updated.version} checkpointed in CTS state machine.`,
      });
    } catch (err: any) {
      addToast({
        type: "error",
        title: "Transition Error",
        message: err.message,
      });
    }
  };

  const handleBatchAdvanceAll = async () => {
    const res = await api.runAllPendingTasks();
    await fetchTasks();
    addToast({
      type: "success",
      title: "Batch Task Execution Complete",
      message: res.message,
    });
  };

  const uniqueDirectives = Array.from(new Set(tasks.map((t) => t.directive_id).filter(Boolean)));
  const displayedTasks = selectedDirectiveFilter === "ALL"
    ? tasks
    : tasks.filter((t) => t.directive_id === selectedDirectiveFilter);

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Kanban className="w-6 h-6 text-cyan-400" />
            <span>Canonical Task State (CTS) Machine</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Deterministic state transitions: PENDING → GRANTED → IN_PROGRESS → COMPLETED with versioning and cryptographic checkpoints.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Directive Filter */}
          <select
            value={selectedDirectiveFilter}
            onChange={(e) => setSelectedDirectiveFilter(e.target.value)}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300 focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">All Directives ({tasks.length} tasks)</option>
            {uniqueDirectives.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>

          <button
            onClick={handleBatchAdvanceAll}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-lg shadow-cyan-600/20 transition-all font-mono"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>1-Click Advance All</span>
          </button>

          <Link
            href="/sandbox"
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-amber-950/40 hover:bg-amber-950/70 border border-amber-800/80 text-amber-300 text-xs font-semibold transition-all font-mono"
          >
            <Box className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>AIO Sandbox Daemon (:18091)</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>

      {/* Kanban Board Columns */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {COLUMNS.map((col) => {
          const colTasks = displayedTasks.filter((t) => t.status === col.id);

          return (
            <div
              key={col.id}
              className="flex flex-col bg-slate-950/60 rounded-xl border border-slate-800/80 p-3 min-h-[500px]"
            >
              {/* Column Header */}
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
                <span className={`text-xs font-semibold uppercase tracking-wider ${col.color}`}>
                  {col.title}
                </span>
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-900 text-slate-400 border border-slate-800">
                  {colTasks.length}
                </span>
              </div>

              {/* Tasks List */}
              <div className="space-y-3 flex-1">
                {colTasks.map((task) => (
                  <div
                    key={task.task_id}
                    onClick={() => setSelectedTask(task)}
                    className="p-3.5 rounded-lg bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition-all cursor-pointer space-y-2.5 shadow-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-slate-200">
                        {task.task_id}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950 text-indigo-400 border border-indigo-900/40">
                        v{task.version}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-indigo-950/80 text-cyan-300 border border-cyan-800/50 font-mono">
                        {task.worker_role}
                      </span>
                      {task.checkpoint_id && (
                        <span className="text-[10px] text-slate-500 font-mono truncate">
                          {task.checkpoint_id}
                        </span>
                      )}
                    </div>

                    <div className="text-[11px] text-slate-400 font-mono truncate">
                      Dir: {task.directive_id}
                    </div>

                    {/* Quick Move Single-Click Action */}
                    <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                      <span className="text-slate-500 font-mono">
                        {task.updated_at ? new Date(task.updated_at).toLocaleTimeString() : "--"}
                      </span>

                      {task.status === "pending" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAdvanceStatus(task.task_id, "granted");
                          }}
                          className="px-2 py-0.5 rounded bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 font-mono text-[10px] flex items-center gap-1 transition-all"
                        >
                          <span>Grant</span>
                          <ArrowRight className="w-2.5 h-2.5" />
                        </button>
                      )}

                      {task.status === "granted" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAdvanceStatus(task.task_id, "in_progress");
                          }}
                          className="px-2 py-0.5 rounded bg-indigo-950 hover:bg-indigo-900 text-indigo-300 border border-indigo-800 font-mono text-[10px] flex items-center gap-1 transition-all"
                        >
                          <span>Execute</span>
                          <ArrowRight className="w-2.5 h-2.5" />
                        </button>
                      )}

                      {task.status === "in_progress" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAdvanceStatus(task.task_id, "completed");
                          }}
                          className="px-2 py-0.5 rounded bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 font-mono text-[10px] flex items-center gap-1 transition-all"
                        >
                          <span>Complete</span>
                          <CheckCircle2 className="w-2.5 h-2.5" />
                        </button>
                      )}

                      {task.status === "held" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAdvanceStatus(task.task_id, "granted");
                          }}
                          className="px-2 py-0.5 rounded bg-amber-950 hover:bg-amber-900 text-amber-300 border border-amber-800 font-mono text-[10px] flex items-center gap-1 transition-all"
                        >
                          <span>Release</span>
                          <RotateCcw className="w-2.5 h-2.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Task Detail Inspector */}
      {selectedTask && (
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Kanban className="w-4 h-4 text-cyan-400" />
              <span className="font-mono text-sm font-bold text-white">{selectedTask.task_id}</span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-950 text-indigo-300 border border-slate-800">
                v{selectedTask.version}
              </span>
            </div>
            <button
              onClick={() => setSelectedTask(null)}
              className="text-xs text-slate-400 hover:text-white"
            >
              Close Inspector
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
              <span className="text-slate-500 block">Worker Role</span>
              <span className="text-cyan-400 font-semibold">{selectedTask.worker_role}</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
              <span className="text-slate-500 block">Status</span>
              <span className="text-emerald-400 font-semibold uppercase">{selectedTask.status}</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
              <span className="text-slate-500 block">Checkpoint</span>
              <span className="text-slate-200 truncate block">{selectedTask.checkpoint_id || "--"}</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
              <span className="text-slate-500 block">Directive ID</span>
              <span className="text-indigo-400 truncate block">{selectedTask.directive_id}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
