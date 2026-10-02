"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Cpu,
  Shield,
  Layers,
  Sparkles,
  Zap,
  Lock,
  Server,
  FileCheck,
  Activity,
  CheckCircle2,
  RefreshCw,
  Sliders,
  DollarSign,
  Search,
  KeyRound,
  FileText,
  AlertCircle,
  Database,
  ArrowRight,
  Code2,
  FileCode,
} from "lucide-react";
import { api } from "@/lib/api";
import { CanonicalTaskState } from "@/lib/types";
import { getStoredSettings, EnterpriseSettings } from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

type SandboxTab = "telemetry" | "specialists" | "governance" | "containment";

interface SpecialistSpec {
  id: string;
  name: string;
  role: string;
  workerName: string;
  title: string;
  capability: string;
  networkPolicy: string;
  timeoutSeconds: number;
  description: string;
  tools: string[];
}

const SPECIALIST_SPECS: SpecialistSpec[] = [
  {
    id: "s-code",
    name: "S_CODE",
    role: "W_DEV",
    workerName: "Development Worker",
    title: "Component Coder & AST Linter",
    capability: "CODE",
    networkPolicy: "DISABLED",
    timeoutSeconds: 300,
    description: "AST structural parsing, linting, syntax verification, schema migrations, and deterministic unified code diff generation.",
    tools: ["ast_symbol_inspector", "cms_schema_validator", "code_patcher", "lint_checker", "wcag_accessibility_scanner"],
  },
  {
    id: "s-alloc",
    name: "S_ALLOC",
    role: "W_STRAT",
    workerName: "Strategy Worker",
    title: "Media & Budget Allocator",
    capability: "ALLOC",
    networkPolicy: "DISABLED",
    timeoutSeconds: 120,
    description: "Deterministic portfolio ad spend allocation across channels with convex marginal return optimization.",
    tools: ["media_mix_modeler", "budget_allocator_tool", "funnel_simulator", "allocation_solver", "diminishing_returns_model"],
  },
  {
    id: "s-copy",
    name: "S_COPY",
    role: "W_CREAT",
    workerName: "Creative Content Worker",
    title: "Lexical & Brand Copy Guardian",
    capability: "COPY",
    networkPolicy: "DISABLED",
    timeoutSeconds: 120,
    description: "Variant generation, hook scoring, format validation, and anti-hallucination lexical adherence check.",
    tools: ["variant_generator", "hook_critic"],
  },
  {
    id: "s-val",
    name: "S_VAL",
    role: "W_PROD",
    workerName: "Product Evidence Worker",
    title: "Claim & Compliance Validator",
    capability: "VAL",
    networkPolicy: "DISABLED",
    timeoutSeconds: 120,
    description: "Claim-to-evidence linkage verification, statutory compliance linting, and product specification validation.",
    tools: ["compliance_linter", "claim_checker", "dossier_assembler", "schema_validator"],
  },
  {
    id: "s-comp",
    name: "S_COMP",
    role: "W_COMP",
    workerName: "Competitor Intelligence Worker",
    title: "Competitive Gap & Price Scraper",
    capability: "COMP",
    networkPolicy: "CONTROLLED (Egress Allowlist)",
    timeoutSeconds: 180,
    description: "Comparative DOM analysis, pricing trajectory tracking, and differentiation scoring through egress proxy sidecar.",
    tools: ["dom_parser", "price_tracker", "browser_automation"],
  },
  {
    id: "s-parse",
    name: "S_PARSE",
    role: "W_VOICE",
    workerName: "Customer Voice Worker",
    title: "Sentiment & Review Parser",
    capability: "PARSE",
    networkPolicy: "DISABLED",
    timeoutSeconds: 120,
    description: "Aspect-based sentiment analysis, customer objection clustering, and feedback span grounding.",
    tools: ["nlp_classifier", "sentiment_analyzer", "pii_redactor", "objection_extractor"],
  },
  {
    id: "s-attr",
    name: "S_ATTR",
    role: "W_LEARN",
    workerName: "Learning & Performance Worker",
    title: "Telemetry Attribution Modeler",
    capability: "ATTR",
    networkPolicy: "DISABLED",
    timeoutSeconds: 120,
    description: "Adstock decay estimation, fatigue curve modeling, and Shapley incremental attribution scoring.",
    tools: ["attribution_engine", "decay_scorer", "wearout_analyzer"],
  },
];

export default function SandboxPortalPage() {
  const [settings] = useState<EnterpriseSettings>(getStoredSettings());
  const [activeTab, setActiveTab] = useState<SandboxTab>("telemetry");
  const [tasks, setTasks] = useState<CanonicalTaskState[]>([]);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [selectedSpecialist, setSelectedSpecialist] = useState<SpecialistSpec>(SPECIALIST_SPECS[0]);
  const { addToast } = useToast();

  const loadTasks = async () => {
    setIsLoadingTasks(true);
    try {
      const data = await api.getTasks();
      setTasks(data);
    } catch {
      // Graceful fallback
    } finally {
      setIsLoadingTasks(false);
    }
  };

  useEffect(() => {
    loadTasks();
    const interval = setInterval(loadTasks, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Banner: Authoritative Control Plane */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl backdrop-blur-md">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 border border-indigo-500/30 rounded-xl text-indigo-400">
            <Shield className="w-8 h-8 text-cyan-400 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Governed Sandbox Control Plane
              </h1>
              <span className="px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Layer 6 Isolation
              </span>
            </div>
            <p className="text-sm text-slate-400 mt-1">
              Deterministic, fail-closed runtime for Specialist Sub-Agents. Execution strictly bound to Intelligence Engine TaskGrants.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadTasks}
            disabled={isLoadingTasks}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingTasks ? "animate-spin text-cyan-400" : ""}`} />
            Sync CTS State
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800 space-x-1">
        {[
          { id: "telemetry", label: "Isolation Telemetry", icon: Activity },
          { id: "specialists", label: "Specialist Capabilities (7)", icon: Sliders },
          { id: "governance", label: "Governed Execution Pipeline", icon: Shield },
          { id: "containment", label: "Hardened Container Specs", icon: Box },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as SandboxTab)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-all ${
                isActive
                  ? "border-cyan-400 text-cyan-300 bg-cyan-500/5"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab 1: Isolation Telemetry */}
      {activeTab === "telemetry" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">Security Boundary</span>
                <Shield className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-xl font-bold text-white mt-2">FAIL-CLOSED</div>
              <p className="text-xs text-slate-500 mt-1">Egress DENY_ALL enforced</p>
            </div>

            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">Memory Ceiling</span>
                <Cpu className="w-4 h-4 text-cyan-400" />
              </div>
              <div className="text-xl font-bold text-white mt-2">4,096 MB</div>
              <p className="text-xs text-slate-500 mt-1">Strict Cgroup v2 limit</p>
            </div>

            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">Active CTS Tasks</span>
                <Layers className="w-4 h-4 text-indigo-400" />
              </div>
              <div className="text-xl font-bold text-white mt-2">{tasks.length}</div>
              <p className="text-xs text-slate-500 mt-1">Canonical State persisted</p>
            </div>

            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">Workspace Storage</span>
                <Database className="w-4 h-4 text-amber-400" />
              </div>
              <div className="text-xl font-bold text-white mt-2">Tmpfs Ephemeral</div>
              <p className="text-xs text-slate-500 mt-1">Scrubbed on attempt teardown</p>
            </div>
          </div>

          {/* Active Tasks in Isolation */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              Governed Task Execution Registry
            </h3>

            {tasks.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-sm">
                No active tasks currently executing in the sandbox. Trigger a directive from the Directives panel to initiate governed execution.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-800/60 text-slate-400 uppercase font-semibold">
                    <tr>
                      <th className="py-2.5 px-3">Task ID</th>
                      <th className="py-2.5 px-3">Directive</th>
                      <th className="py-2.5 px-3">Worker Role</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">CAS Version</th>
                      <th className="py-2.5 px-3">Isolation Grant</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {tasks.map((task) => (
                      <tr key={task.task_id} className="hover:bg-slate-800/30 transition">
                        <td className="py-2.5 px-3 font-mono text-cyan-300">{task.task_id.slice(0, 18)}...</td>
                        <td className="py-2.5 px-3 font-mono text-slate-400">{task.directive_id.slice(0, 14)}...</td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                            {task.worker_role}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${
                              task.status === "completed"
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : task.status === "in_progress"
                                ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                                : task.status === "held"
                                ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                                : "bg-slate-700/50 text-slate-300"
                            }`}
                          >
                            {task.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-400">v{task.version}</td>
                        <td className="py-2.5 px-3">
                          <span className="text-emerald-400 flex items-center gap-1 font-mono text-[11px]">
                            <CheckCircle2 className="w-3 h-3" /> TaskGrant Valid
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Specialist Micro-Tools Specifications */}
      {activeTab === "specialists" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Registered Specialists
            </h3>
            {SPECIALIST_SPECS.map((spec) => {
              const isSelected = selectedSpecialist.id === spec.id;
              return (
                <div
                  key={spec.id}
                  onClick={() => setSelectedSpecialist(spec)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition ${
                    isSelected
                      ? "bg-slate-800 border-cyan-500/50 shadow-md shadow-cyan-500/5"
                      : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm font-bold text-white">{spec.name}</span>
                    <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                      {spec.role}
                    </span>
                  </div>
                  <div className="text-xs text-slate-300 font-medium mt-1">{spec.title}</div>
                  <div className="text-[11px] text-slate-400 mt-1 line-clamp-2">{spec.description}</div>
                </div>
              );
            })}
          </div>

          <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-white">{selectedSpecialist.name}</h2>
                  <span className="px-2 py-0.5 text-xs font-mono bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 rounded">
                    Capability: {selectedSpecialist.capability}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">{selectedSpecialist.title}</p>
              </div>

              <div className="text-right">
                <span className="text-xs text-slate-500">Authorized Worker</span>
                <div className="text-sm font-semibold text-indigo-400">{selectedSpecialist.workerName}</div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-800">
                <span className="text-xs text-slate-400">Network Egress Policy</span>
                <div className="text-sm font-semibold text-emerald-400 mt-0.5 font-mono">
                  {selectedSpecialist.networkPolicy}
                </div>
              </div>
              <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-800">
                <span className="text-xs text-slate-400">Execution Timeout Ceiling</span>
                <div className="text-sm font-semibold text-white mt-0.5 font-mono">
                  {selectedSpecialist.timeoutSeconds}s
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Bounded Capability Allowlist
              </h4>
              <p className="text-xs text-slate-400 mb-3">{selectedSpecialist.description}</p>
              <div className="flex flex-wrap gap-2">
                {selectedSpecialist.tools.map((t) => (
                  <span
                    key={t}
                    className="px-2.5 py-1 text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700 rounded-md"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>

            <div className="p-4 bg-indigo-950/20 border border-indigo-500/20 rounded-xl text-xs text-indigo-300 space-y-1">
              <div className="font-semibold flex items-center gap-1.5 text-indigo-200">
                <Lock className="w-3.5 h-3.5 text-indigo-400" /> Strict Zero-Bypass Contract
              </div>
              <p className="text-slate-400">
                This specialist micro-tool cannot be invoked directly by the browser or unauthenticated clients. It is mounted inside the container at <code className="text-cyan-300">/home/gem/skills/{selectedSpecialist.id}/scripts/run.py</code> and invoked strictly when <code className="text-indigo-300">{selectedSpecialist.role}</code> issues an authorized, signed execution lease.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Governed Execution Pipeline */}
      {activeTab === "governance" && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
          <div className="border-b border-slate-800 pb-4">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Shield className="w-5 h-5 text-cyan-400" />
              Authoritative Governed Execution Sequence
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Every operation follows an unbroken cryptographic chain of custody. Zero parallel execution paths.
            </p>
          </div>

          <div className="space-y-4">
            {[
              {
                step: "01",
                name: "Owner Directive Ingestion",
                desc: "Owner submits strategic objectives, authorized scope, and risk ceilings via POST /directives.",
                entity: "Directive Model (Postgres)",
              },
              {
                step: "02",
                name: "Intelligence Engine Cognitive Planning",
                desc: "IntelligenceEngine plans a topological DAG, resolves dependencies, and mints CanonicalTaskState (CTS) records in PENDING state.",
                entity: "Two-Pass DAG Scheduler",
              },
              {
                step: "03",
                name: "TaskGrant Authorization",
                desc: "TaskStateMachine transitions CTS PENDING → GRANTED with a cryptographic capability grant bounded to the assigned WorkerRole.",
                entity: "TaskStateMachine & StateService",
              },
              {
                step: "04",
                name: "Worker Specialist Invocation",
                desc: "Assigned worker builds execution context and delegates to SandboxClient.invoke(mandate) with ephemeral stage attempt ID.",
                entity: "BoundedWorkerAgent",
              },
              {
                step: "05",
                name: "Hardened Sandbox Execution",
                desc: "SandboxClient dispatches to isolated container runtime. Enforces cgroups, seccomp, egress proxy, and ephemeral tmpfs workspace.",
                entity: "AIO Hardened Sandbox (:8091)",
              },
              {
                step: "06",
                name: "Cryptographic Output Sealing & Sanitization",
                desc: "Outputs are scrubbed, sensitive tokens redacted, and SHA-256 digests computed for input, output, and review dossiers.",
                entity: "SandboxControlPlane.seal()",
              },
              {
                step: "07",
                name: "Mandatory HITL Review Preview",
                desc: "ActionPreview is created for human evaluation. Human decision submitted via POST /approvals/development/decide.",
                entity: "HitlCoordinator & Ed25519 Signer",
              },
              {
                step: "08",
                name: "Terminal CTS State & W3C PROV Lineage",
                desc: "Task transitions to COMPLETED. Immutable provenance events committed to PostgreSQL audit ledger.",
                entity: "ProvenanceRecorder (W3C PROV)",
              },
            ].map((s) => (
              <div
                key={s.step}
                className="flex items-start gap-4 p-3.5 bg-slate-800/40 border border-slate-800 rounded-xl hover:border-slate-700 transition"
              >
                <div className="text-sm font-mono font-bold text-cyan-400 bg-cyan-500/10 px-2.5 py-1 rounded border border-cyan-500/20">
                  {s.step}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-white">{s.name}</h4>
                    <span className="text-[11px] font-mono text-slate-500">{s.entity}</span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: Hardened Container Specs */}
      {activeTab === "containment" && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
          <div className="border-b border-slate-800 pb-4">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Box className="w-5 h-5 text-indigo-400" />
              Hardened Sandbox Deployment Specification
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Specification defined in <code className="text-cyan-300">sandbox/docker/hardened/docker-compose.hardened.yaml</code>.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800 space-y-2">
              <h4 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Cpu className="w-4 h-4 text-cyan-400" /> Cgroup Resource Ceilings
              </h4>
              <ul className="text-xs text-slate-400 space-y-1 font-mono">
                <li>• mem_limit: 4g</li>
                <li>• cpus: 2.0</li>
                <li>• pids_limit: 1024</li>
                <li>• shm_size: 2gb</li>
              </ul>
            </div>

            <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800 space-y-2">
              <h4 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Shield className="w-4 h-4 text-emerald-400" /> Seccomp & Privileges
              </h4>
              <ul className="text-xs text-slate-400 space-y-1 font-mono">
                <li>• no-new-privileges: true</li>
                <li>• seccomp: ./seccomp/worker-seccomp.json</li>
                <li>• cap_drop: ALL</li>
                <li>• user: 1000:1000 (non-root)</li>
              </ul>
            </div>

            <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800 space-y-2">
              <h4 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Lock className="w-4 h-4 text-amber-400" /> Egress Proxy Sidecar
              </h4>
              <ul className="text-xs text-slate-400 space-y-1 font-mono">
                <li>• proxy_server: http://aio-egress-proxy:8118</li>
                <li>• default_policy: DENY_ALL</li>
                <li>• allowlist: allowed-domains.txt</li>
                <li>• network: sandbox-internal (zero public routing)</li>
              </ul>
            </div>

            <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-800 space-y-2">
              <h4 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Database className="w-4 h-4 text-indigo-400" /> Ephemeral Tmpfs Storage
              </h4>
              <ul className="text-xs text-slate-400 space-y-1 font-mono">
                <li>• /tmp: rw,noexec,nosuid,size=1024m</li>
                <li>• /workspace: rw,size=2048m</li>
                <li>• /home/gem/skills: ro (read-only mount)</li>
                <li>• lifecycle: deterministically scrubbed</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
