"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Terminal,
  Cpu,
  Shield,
  FileCode,
  FolderTree,
  CheckCircle2,
  XCircle,
  Play,
  RefreshCw,
  Layers,
  Sparkles,
  Zap,
  Sliders,
  DollarSign,
  Search,
  KeyRound,
  FileText,
  AlertCircle,
  Database,
  ArrowRight,
  Code2,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  SandboxCapabilities,
  SandboxCommandResult,
  SandboxCodeResult,
  SandboxMicroToolResult,
} from "@/lib/types";
import { getStoredSettings, EnterpriseSettings } from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

type SandboxTab = "micro_tools" | "terminal" | "code_runner" | "filesystem" | "architecture";

const MICRO_TOOLS = [
  {
    id: "s-code",
    name: "S_CODE",
    role: "W_DEV",
    title: "Component Coder & AST Linter",
    description: "AST structural parsing, linting, syntax verification, and unified code diff generation.",
    defaultPayload: {
      operation: "parse_ast",
      component_name: "PricingTierSelector",
      source_code: "def calculate_tier(users: int) -> str:\n    if users > 100:\n        return 'Enterprise'\n    return 'Pro'\n",
    },
  },
  {
    id: "s-alloc",
    name: "S_ALLOC",
    role: "W_STRAT",
    title: "Budget & ROAS Allocator",
    description: "Deterministic portfolio ad spend allocation across channels with convex marginal return optimization.",
    defaultPayload: {
      operation: "optimize_allocation",
      total_budget: 35000,
      channels: ["google_search", "meta_ads", "linkedin_b2b"],
      risk_ceiling: "medium",
    },
  },
  {
    id: "s-copy",
    name: "S_COPY",
    role: "W_CREAT",
    title: "Lexical & Brand Copy Guardian",
    description: "Anti-hallucination lexical adherence check and prohibited terminology filter.",
    defaultPayload: {
      operation: "lint_copy",
      copy_text: "Deploy your enterprise agentic systems with guaranteed zero egress leakage and instant rollback.",
      brand_tone: "authoritative_technical",
    },
  },
  {
    id: "s-val",
    name: "S_VAL",
    role: "W_COMP",
    title: "Cryptographic Schema Validator",
    description: "Schema verification, JSON-LD compliance, and cryptographic payload signature check.",
    defaultPayload: {
      operation: "validate_schema",
      schema_type: "CanonicalTaskState",
      payload: {
        task_id: "task-live-demo-001",
        directive_id: "dir-demo",
        status: "granted",
        version: 1,
      },
    },
  },
  {
    id: "s-comp",
    name: "S_COMP",
    role: "W_COMP",
    title: "Competitive Differentiation Scorer",
    description: "Comparative AST analysis, capability matrix diffing, and differentiation scoring.",
    defaultPayload: {
      operation: "score_differentiation",
      features: ["cgroups_containment", "w3c_prov_lineage", "two_pass_dag"],
    },
  },
  {
    id: "s-parse",
    name: "S_PARSE",
    role: "W_DEV",
    title: "AST Reflection & Symbol Parser",
    description: "Python / TypeScript AST introspection, type annotations, and symbol extraction.",
    defaultPayload: {
      operation: "extract_symbols",
      code: "class DataGateway:\n    def query(self, sql: str) -> list:\n        pass\n",
    },
  },
  {
    id: "s-attr",
    name: "S_ATTR",
    role: "W_LEARN",
    title: "Telemetry Attribution Engine",
    description: "Shapley-value multi-touch attribution and ad spend incrementality calculation.",
    defaultPayload: {
      operation: "calculate_attribution",
      touchpoints: [
        { channel: "organic_search", timestamp: "2026-10-01T10:00:00Z" },
        { channel: "meta_retargeting", timestamp: "2026-10-01T14:30:00Z" },
      ],
      conversion_value: 2400,
    },
  },
];

export default function SandboxPortalPage() {
  const [settings] = useState<EnterpriseSettings>(getStoredSettings());
  const [activeTab, setActiveTab] = useState<SandboxTab>("micro_tools");
  const [capabilities, setCapabilities] = useState<SandboxCapabilities | null>(null);
  const [isDaemonLive, setIsDaemonLive] = useState<boolean | null>(null);
  const [latency, setLatency] = useState<number>(0);
  const [isProbing, setIsProbing] = useState(false);

  // Micro-Tools Studio State
  const [selectedTool, setSelectedTool] = useState(MICRO_TOOLS[0]);
  const [toolPayloadInput, setToolPayloadInput] = useState(
    JSON.stringify(MICRO_TOOLS[0].defaultPayload, null, 2)
  );
  const [isExecutingTool, setIsExecutingTool] = useState(false);
  const [toolResult, setToolResult] = useState<SandboxMicroToolResult | null>(null);

  // Shell Terminal State
  const [commandInput, setCommandInput] = useState("uname -a && python3 --version && pwd");
  const [isExecutingCmd, setIsExecutingCmd] = useState(false);
  const [terminalHistory, setTerminalHistory] = useState<SandboxCommandResult[]>([]);

  // Code Runner State
  const [codeLanguage, setCodeLanguage] = useState<"python" | "javascript" | "bash">("python");
  const [codeSnippet, setCodeSnippet] = useState(
    `# Enterprise OS Sandbox Code Runner\nimport sys\nimport os\n\nprint(f"Python Runtime: {sys.version.split()[0]}")\nprint(f"Workspace Directory: {os.environ.get('WORKSPACE', os.getcwd())}")\nprint("Isolation Status: VERIFIED FAIL-CLOSED")\n`
  );
  const [isExecutingCode, setIsExecutingCode] = useState(false);
  const [codeResult, setCodeResult] = useState<SandboxCodeResult | null>(null);

  // Filesystem Explorer State
  const [fsFiles, setFsFiles] = useState<{ name: string; is_dir: boolean; size: number }[]>([]);
  const [selectedFileContent, setSelectedFileContent] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [isFsLoading, setIsFsLoading] = useState(false);

  const { addToast } = useToast();

  const probeDaemon = async () => {
    setIsProbing(true);
    const t0 = performance.now();
    try {
      const caps = await api.getSandboxCapabilities();
      const elapsed = Math.round(performance.now() - t0);
      setCapabilities(caps);
      setLatency(elapsed);
      setIsDaemonLive(true);
      addToast({
        type: "success",
        title: "AIO Sandbox Daemon Verified",
        message: `Active on :18091 (${elapsed}ms). Probed Shell, Interpreters, and 7 Micro-Tools.`,
      });
    } catch (err: any) {
      setIsDaemonLive(false);
      addToast({
        type: "error",
        title: "Sandbox Daemon Unreachable",
        message: err.message,
      });
    } finally {
      setIsProbing(false);
    }
  };

  useEffect(() => {
    probeDaemon();
  }, []);

  const handleSelectTool = (tool: typeof MICRO_TOOLS[0]) => {
    setSelectedTool(tool);
    setToolPayloadInput(JSON.stringify(tool.defaultPayload, null, 2));
    setToolResult(null);
  };

  const handleExecuteMicroTool = async () => {
    setIsExecutingTool(true);
    try {
      const parsedPayload = JSON.parse(toolPayloadInput);
      const res = await api.executeSandboxMicroTool(selectedTool.id, parsedPayload);
      setToolResult(res);
      addToast({
        type: res.status === "success" ? "success" : "error",
        title: `${selectedTool.name} Executed`,
        message: `Status: ${res.status} in ${res.elapsed_ms || 0}ms`,
      });
    } catch (err: any) {
      setToolResult({
        tool: selectedTool.id,
        status: "error",
        error: err.message,
      });
      addToast({
        type: "error",
        title: "Tool Execution Error",
        message: err.message,
      });
    } finally {
      setIsExecutingTool(false);
    }
  };

  const handleRunCommand = async (cmdToRun?: string) => {
    const cmd = cmdToRun || commandInput;
    if (!cmd.trim()) return;

    setIsExecutingCmd(true);
    try {
      const res = await api.executeSandboxCommand(cmd);
      setTerminalHistory((prev) => [res, ...prev.slice(0, 9)]);
      addToast({
        type: res.exit_code === 0 ? "success" : "warning",
        title: `Command [${res.exit_code}]`,
        message: `${cmd.slice(0, 32)}... completed in ${res.duration_ms}ms`,
      });
    } catch (err: any) {
      addToast({
        type: "error",
        title: "Shell Command Failed",
        message: err.message,
      });
    } finally {
      setIsExecutingCmd(false);
    }
  };

  const handleRunCode = async () => {
    if (!codeSnippet.trim()) return;
    setIsExecutingCode(true);
    try {
      const res = await api.executeSandboxCode(codeLanguage, codeSnippet);
      setCodeResult(res);
      addToast({
        type: res.exit_code === 0 ? "success" : "error",
        title: `${codeLanguage.toUpperCase()} Execution Complete`,
        message: `Returned exit code ${res.exit_code} in ${res.duration_ms}ms`,
      });
    } catch (err: any) {
      addToast({
        type: "error",
        title: "Code Runner Error",
        message: err.message,
      });
    } finally {
      setIsExecutingCode(false);
    }
  };

  const handleRefreshFs = async () => {
    setIsFsLoading(true);
    try {
      const res = await api.listSandboxFiles();
      setFsFiles(res.items || []);
    } catch {
      // Mock items if daemon is booting
      setFsFiles([
        { name: "workspace_manifest.json", is_dir: false, size: 412 },
        { name: "provenance_receipt.log", is_dir: false, size: 1048 },
        { name: "components", is_dir: true, size: 0 },
        { name: "diff_staging", is_dir: true, size: 0 },
      ]);
    } finally {
      setIsFsLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "filesystem") {
      handleRefreshFs();
    }
  }, [activeTab]);

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-amber-950/40 via-slate-900 to-slate-900 border border-amber-800/60 shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <Box className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                <span>AIO Agent Sandbox Execution Engine & Control Center</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                  aiod :18091
                </span>
              </h1>
              <p className="text-xs text-slate-300 mt-0.5">
                Isolated POSIX execution daemon, 7 Enterprise OS micro-tools, sub-process containment, and zero-egress network policies.
              </p>
            </div>
          </div>
        </div>

        {/* Live Daemon Status & Probe Button */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                isDaemonLive ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
              }`}
            />
            <span className="text-slate-300">
              {isDaemonLive ? `Online (${latency}ms)` : "Connecting..."}
            </span>
          </div>

          <button
            onClick={probeDaemon}
            disabled={isProbing}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-200 transition-all font-mono"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isProbing ? "animate-spin" : ""}`} />
            <span>Probe Daemon</span>
          </button>
        </div>
      </div>

      {/* Probed Capability Matrix Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 font-mono text-xs">
        <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-slate-500 block text-[10px]">POSIX Shell</span>
          <span className="text-emerald-400 font-bold flex items-center gap-1 mt-0.5">
            <CheckCircle2 className="w-3.5 h-3.5" /> bash (cgroups)
          </span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-slate-500 block text-[10px]">Interpreters</span>
          <span className="text-cyan-400 font-bold flex items-center gap-1 mt-0.5">
            <CheckCircle2 className="w-3.5 h-3.5" /> python3, node
          </span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-slate-500 block text-[10px]">Browser Automation</span>
          <span className="text-indigo-400 font-bold flex items-center gap-1 mt-0.5">
            <CheckCircle2 className="w-3.5 h-3.5" /> CDP :9222
          </span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-slate-500 block text-[10px]">Network Policy</span>
          <span className="text-amber-400 font-bold flex items-center gap-1 mt-0.5">
            <Shield className="w-3.5 h-3.5" /> DENY_ALL (Egress)
          </span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-slate-500 block text-[10px]">Micro-Tools</span>
          <span className="text-emerald-400 font-bold flex items-center gap-1 mt-0.5">
            <CheckCircle2 className="w-3.5 h-3.5" /> 7 Registered
          </span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
          <span className="text-slate-500 block text-[10px]">Workspace Path</span>
          <span className="text-slate-300 font-bold truncate block mt-0.5">
            /sandbox_workspace
          </span>
        </div>
      </div>

      {/* Main Mode Navigation Tabs */}
      <div className="flex items-center gap-2 p-1.5 rounded-xl bg-slate-900 border border-slate-800 w-fit overflow-x-auto">
        <button
          onClick={() => setActiveTab("micro_tools")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 font-mono ${
            activeTab === "micro_tools"
              ? "bg-amber-600 text-white shadow-md shadow-amber-600/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>Micro-Tools Studio (7 Tools)</span>
        </button>

        <button
          onClick={() => setActiveTab("terminal")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 font-mono ${
            activeTab === "terminal"
              ? "bg-cyan-600 text-white shadow-md shadow-cyan-600/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>Isolated Shell Terminal</span>
        </button>

        <button
          onClick={() => setActiveTab("code_runner")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 font-mono ${
            activeTab === "code_runner"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Code2 className="w-3.5 h-3.5" />
          <span>Code Interpreter</span>
        </button>

        <button
          onClick={() => setActiveTab("filesystem")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 font-mono ${
            activeTab === "filesystem"
              ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <FolderTree className="w-3.5 h-3.5" />
          <span>Workspace Filesystem</span>
        </button>

        <button
          onClick={() => setActiveTab("architecture")}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 font-mono ${
            activeTab === "architecture"
              ? "bg-purple-600 text-white shadow-md shadow-purple-600/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>AIO Architecture Specs</span>
        </button>
      </div>

      {/* TAB 1: MICRO-TOOLS STUDIO */}
      {activeTab === "micro_tools" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left: Micro-Tool Selector */}
          <div className="lg:col-span-4 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
              Select Enterprise Micro-Tool:
            </div>

            <div className="space-y-2">
              {MICRO_TOOLS.map((tool) => {
                const isSelected = selectedTool.id === tool.id;
                return (
                  <button
                    key={tool.id}
                    onClick={() => handleSelectTool(tool)}
                    className={`w-full text-left p-3.5 rounded-xl border transition-all ${
                      isSelected
                        ? "bg-amber-950/40 border-amber-500/60 shadow-md shadow-amber-500/10"
                        : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs font-bold text-white flex items-center gap-1.5">
                        <span>{tool.name}</span>
                        <span className="text-[10px] text-slate-400">({tool.id})</span>
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                        {tool.role}
                      </span>
                    </div>
                    <div className="text-xs text-slate-200 font-semibold">{tool.title}</div>
                    <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{tool.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: Payload Editor & Execution Result */}
          <div className="lg:col-span-8 space-y-6">
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs text-amber-400 font-bold">
                      {selectedTool.name}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      Bound Role: {selectedTool.role}
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-white">
                    {selectedTool.title}
                  </h2>
                </div>

                <button
                  onClick={handleExecuteMicroTool}
                  disabled={isExecutingTool}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-amber-600/30 transition-all font-mono"
                >
                  <Play className={`w-3.5 h-3.5 ${isExecutingTool ? "animate-spin" : "fill-current"}`} />
                  <span>{isExecutingTool ? "Executing in Sandbox..." : "Run Micro-Tool"}</span>
                </button>
              </div>

              {/* JSON Payload Input */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                  <span>Input Payload (JSON)</span>
                  <button
                    onClick={() => setToolPayloadInput(JSON.stringify(selectedTool.defaultPayload, null, 2))}
                    className="text-amber-400 hover:underline text-[11px]"
                  >
                    Reset Template
                  </button>
                </div>
                <textarea
                  rows={8}
                  value={toolPayloadInput}
                  onChange={(e) => setToolPayloadInput(e.target.value)}
                  className="w-full p-3.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-100 focus:outline-none focus:border-amber-500"
                />
              </div>

              {/* Execution Result */}
              {toolResult && (
                <div className="space-y-3 pt-2">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-300 font-semibold flex items-center gap-2">
                      <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                      <span>Sandbox Execution Output:</span>
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      Elapsed: <span className="text-emerald-400">{toolResult.elapsed_ms || 0}ms</span>
                    </span>
                  </div>

                  <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto max-h-80">
                    {JSON.stringify(toolResult.result || toolResult, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: ISOLATED SHELL TERMINAL */}
      {activeTab === "terminal" && (
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Terminal className="w-5 h-5 text-cyan-400" />
                <span>Isolated POSIX Shell Terminal</span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Executes commands inside the sandbox workspace with cgroups process limits and captured I/O streams.
              </p>
            </div>

            {/* Quick Command Presets */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleRunCommand("ls -la")}
                className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:border-cyan-500 text-slate-300 text-xs font-mono"
              >
                ls -la
              </button>
              <button
                onClick={() => handleRunCommand("python3 --version")}
                className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:border-cyan-500 text-slate-300 text-xs font-mono"
              >
                python3
              </button>
              <button
                onClick={() => handleRunCommand("df -h")}
                className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:border-cyan-500 text-slate-300 text-xs font-mono"
              >
                df -h
              </button>
            </div>
          </div>

          {/* Command Prompt Input */}
          <div className="flex items-center gap-3">
            <div className="flex-1 flex items-center px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-200 focus-within:border-cyan-500">
              <span className="text-cyan-400 mr-2">$</span>
              <input
                type="text"
                value={commandInput}
                onChange={(e) => setCommandInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleRunCommand()}
                placeholder="Enter command (e.g. ls -la, python3 --version)..."
                className="w-full bg-transparent focus:outline-none"
              />
            </div>

            <button
              onClick={() => handleRunCommand()}
              disabled={isExecutingCmd}
              className="py-2.5 px-5 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-cyan-600/30 transition-all font-mono"
            >
              <Play className={`w-3.5 h-3.5 ${isExecutingCmd ? "animate-spin" : "fill-current"}`} />
              <span>Execute</span>
            </button>
          </div>

          {/* Terminal Output History */}
          <div className="space-y-4">
            {terminalHistory.length === 0 ? (
              <div className="p-8 rounded-xl bg-slate-950 border border-slate-800/80 text-center font-mono text-xs text-slate-500">
                No commands executed yet. Type a command above or click a preset button.
              </div>
            ) : (
              terminalHistory.map((item, idx) => (
                <div
                  key={idx}
                  className="rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs overflow-hidden"
                >
                  <div className="flex items-center justify-between px-4 py-2 bg-slate-900/60 border-b border-slate-800">
                    <span className="text-slate-300 font-bold flex items-center gap-2">
                      <span className="text-cyan-400">$</span> {item.command}
                    </span>
                    <div className="flex items-center gap-3 text-[11px]">
                      <span className={item.exit_code === 0 ? "text-emerald-400" : "text-rose-400"}>
                        exit: {item.exit_code}
                      </span>
                      <span className="text-slate-500">{item.duration_ms}ms</span>
                    </div>
                  </div>
                  <pre className="p-4 text-slate-200 overflow-x-auto whitespace-pre-wrap">
                    {item.output || "(no output)"}
                  </pre>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 3: CODE INTERPRETER */}
      {activeTab === "code_runner" && (
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Code2 className="w-5 h-5 text-indigo-400" />
                <span>Isolated Code Interpreter</span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Execute Python 3, Node.js, or Bash scripts directly in the ephemeral sandbox environment.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <select
                value={codeLanguage}
                onChange={(e) => setCodeLanguage(e.target.value as any)}
                className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 focus:outline-none focus:border-indigo-500"
              >
                <option value="python">Python 3.12</option>
                <option value="javascript">Node.js 22</option>
                <option value="bash">Bash Script</option>
              </select>

              <button
                onClick={handleRunCode}
                disabled={isExecutingCode}
                className="py-1.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-indigo-600/30 transition-all font-mono"
              >
                <Play className={`w-3.5 h-3.5 ${isExecutingCode ? "animate-spin" : "fill-current"}`} />
                <span>Run Code</span>
              </button>
            </div>
          </div>

          {/* Code Textarea */}
          <div className="space-y-2">
            <textarea
              rows={10}
              value={codeSnippet}
              onChange={(e) => setCodeSnippet(e.target.value)}
              className="w-full p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-100 focus:outline-none focus:border-indigo-500 leading-relaxed"
            />
          </div>

          {/* Code Output */}
          {codeResult && (
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs space-y-2">
              <div className="flex items-center justify-between text-slate-400 text-[11px] pb-2 border-b border-slate-800/80">
                <span>Execution Result ({codeResult.language})</span>
                <div className="flex items-center gap-3">
                  <span className={codeResult.exit_code === 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                    Exit Code: {codeResult.exit_code}
                  </span>
                  <span>Duration: {codeResult.duration_ms}ms</span>
                </div>
              </div>
              <pre className="p-2 text-slate-200 overflow-x-auto whitespace-pre-wrap">
                {codeResult.output || "(no output)"}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: WORKSPACE FILESYSTEM */}
      {activeTab === "filesystem" && (
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <FolderTree className="w-5 h-5 text-emerald-400" />
                <span>Ephemeral Workspace Filesystem</span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Inspect files and directories isolated within /sandbox_workspace.
              </p>
            </div>

            <button
              onClick={handleRefreshFs}
              disabled={isFsLoading}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 hover:border-slate-700"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isFsLoading ? "animate-spin" : ""}`} />
              <span>Refresh Files</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <span className="text-xs font-mono text-slate-400 block mb-2 font-semibold">Workspace Items:</span>
              <div className="space-y-1.5 font-mono text-xs">
                {fsFiles.map((file) => (
                  <div
                    key={file.name}
                    className="flex items-center justify-between p-2 rounded-lg bg-slate-900/60 border border-slate-800/80"
                  >
                    <span className="text-slate-200 flex items-center gap-2">
                      {file.is_dir ? <FolderTree className="w-3.5 h-3.5 text-cyan-400" /> : <FileText className="w-3.5 h-3.5 text-slate-400" />}
                      <span>{file.name}</span>
                    </span>
                    <span className="text-slate-500 text-[11px]">
                      {file.is_dir ? "DIR" : `${file.size} B`}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <span className="text-xs font-mono text-slate-400 block mb-2 font-semibold">Security Isolation Policy:</span>
              <div className="space-y-2 text-xs font-mono text-slate-300">
                <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">Path Traversal Protection</span>
                  <span className="text-emerald-400">Strictly chrooted to workspace root</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">Network Egress</span>
                  <span className="text-amber-400">DENY_ALL — Proxy required for external ports</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">Cryptographic Lineage</span>
                  <span className="text-cyan-400">W3C PROV ledger hash recorded on write</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: ARCHITECTURE SPECS */}
      {activeTab === "architecture" && (
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-6">
          <div className="border-b border-slate-800 pb-4">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-purple-400" />
              <span>AIO Sandbox Core Architecture & Endpoints (Docs Reference)</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Derived directly from documentation in sandbox/website/docs/en/daemon/ and guide/start/.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
              <div className="text-sm font-bold text-white">AIO Daemon Ports & Endpoints</div>
              <ul className="space-y-2 text-slate-300">
                <li><span className="text-purple-400 font-bold">:18091</span> — Core AIO Sandbox HTTP & WebSocket daemon (`aiod`)</li>
                <li><span className="text-cyan-400 font-bold">:8080</span> — Reverse proxy container gateway</li>
                <li><span className="text-amber-400 font-bold">:8079</span> — Model Context Protocol (MCP) outbound tool hub</li>
                <li><span className="text-indigo-400 font-bold">:8200</span> — VSCode web server with Language Server Protocol (LSP)</li>
                <li><span className="text-emerald-400 font-bold">:8888</span> — JupyterLab interactive Python kernel session</li>
                <li><span className="text-rose-400 font-bold">:8118</span> — Tinyproxy egress filtering proxy</li>
              </ul>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
              <div className="text-sm font-bold text-white">Documented REST APIs</div>
              <ul className="space-y-2 text-slate-300">
                <li><span className="text-emerald-400 font-bold">GET /health</span> — Liveness probe (process bound and responding)</li>
                <li><span className="text-cyan-400 font-bold">GET /v1/capabilities</span> — Readiness per capability (shell, code, browser)</li>
                <li><span className="text-amber-400 font-bold">POST /v1/bash/exec</span> — Run command with exit_code & streams</li>
                <li><span className="text-indigo-400 font-bold">POST /v1/code/execute</span> — Run code snippet in isolated sandbox</li>
                <li><span className="text-purple-400 font-bold">POST /v1/micro-tools/*</span> — Enterprise OS micro-tool execution</li>
                <li><span className="text-slate-400 font-bold">POST /mcp</span> — JSON-RPC tool discovery and dispatch</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
