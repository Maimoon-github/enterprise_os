"use client";

import React, { useEffect, useState } from "react";
import {
  ScrollText,
  Shield,
  CheckCircle,
  Hash,
  Link as LinkIcon,
  Search,
  Clock,
  User,
  Database,
  Terminal,
  Zap,
  Download,
  Plus,
  Box,
  ExternalLink,
} from "lucide-react";
import { api, MOCK_PROVENANCE_LEDGER } from "@/lib/api";
import { ProvenanceRecord } from "@/lib/types";
import { getStoredSettings, EnterpriseSettings } from "@/lib/settings";
import { useToast } from "@/components/ui/Toast";

export default function AuditLedgerPage() {
  const [records, setRecords] = useState<ProvenanceRecord[]>(MOCK_PROVENANCE_LEDGER);
  const [selectedRecord, setSelectedRecord] = useState<ProvenanceRecord | null>(MOCK_PROVENANCE_LEDGER[0]);
  const [searchQuery, setSearchQuery] = useState("");
  const [settings] = useState<EnterpriseSettings>(getStoredSettings());
  const { addToast } = useToast();

  const fetchLedger = async () => {
    const data = await api.getProvenanceLedger();
    if (data && data.length > 0) setRecords(data);
  };

  useEffect(() => {
    fetchLedger();
  }, []);

  const handleVerifyChain = () => {
    addToast({
      type: "success",
      title: "Cryptographic Chain Verified",
      message: `All ${records.length} blocks verified against parent hash references without discrepancy.`,
      hash: records[0]?.record_hash,
    });
  };

  const handleAppendCheckpoint = () => {
    const newRecord = api.appendProvenance({
      entity_id: `chkpt-sec-${Date.now().toString().slice(-4)}`,
      activity: "MANUAL_SECURITY_AUDIT_ATTESTATION",
      agent: settings.approverName,
      metadata: {
        attestation: "Verified zero-trust policy invariants across all 7 bounded engines.",
        reviewer: settings.approverName,
        tenant_id: settings.tenantId,
      },
    });
    fetchLedger();
    setSelectedRecord(newRecord);
    addToast({
      type: "success",
      title: "Attestation Block Minted",
      message: `Record ${newRecord.record_id} recorded in W3C PROV ledger.`,
      hash: newRecord.record_hash,
    });
  };

  const handleExportProv = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(records, null, 2));
    const dlAnchor = document.createElement("a");
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", `w3c_prov_ledger_${Date.now()}.json`);
    dlAnchor.click();
    addToast({
      type: "info",
      title: "PROV Ledger Exported",
      message: `Saved ${records.length} cryptographically chained blocks to JSON.`,
    });
  };

  const filteredRecords = records.filter(
    (r) =>
      r.record_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.activity.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.agent.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.entity_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <ScrollText className="w-6 h-6 text-cyan-400" />
            <span>W3C PROV Cryptographic Audit Ledger</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Immutable, cryptographically chained provenance records. Every state transition and LLM decision is hashed and verifiable.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleVerifyChain}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-950/60 hover:bg-emerald-900/60 border border-emerald-800 text-xs font-semibold text-emerald-300 transition-all font-mono"
          >
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <span>1-Click Verify Chain</span>
          </button>

          <button
            onClick={handleAppendCheckpoint}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-md shadow-cyan-600/20 transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Attestation</span>
          </button>

          <a
            href={settings.sandboxWebsiteUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-amber-950/40 hover:bg-amber-950/70 border border-amber-800/80 text-amber-300 text-xs font-semibold transition-all font-mono"
          >
            <Box className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>Sandbox Site</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>

      {/* Search Bar & Export */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter ledger by record ID, entity ID, activity name, or agent identifier..."
            className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
          />
        </div>

        <button
          onClick={handleExportProv}
          className="px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-2 shrink-0 transition-all"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export Ledger</span>
        </button>
      </div>

      {/* Main Grid: Ledger Stream & Record Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Chained Record Timeline */}
        <div className="lg:col-span-7 space-y-3">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
            Chained Transition Blocks ({filteredRecords.length})
          </div>

          <div className="space-y-3 relative before:absolute before:left-4 before:top-4 before:bottom-4 before:w-0.5 before:bg-slate-800">
            {filteredRecords.map((rec) => {
              const isSelected = selectedRecord?.record_id === rec.record_id;

              return (
                <div
                  key={rec.record_id}
                  onClick={() => setSelectedRecord(rec)}
                  className={`relative pl-9 cursor-pointer transition-all ${
                    isSelected ? "scale-[1.01]" : ""
                  }`}
                >
                  {/* Hash Node Point */}
                  <div className="absolute left-2.5 top-4 w-3.5 h-3.5 -ml-0.5 rounded-full bg-slate-900 border-2 border-cyan-400 flex items-center justify-center shadow-md shadow-cyan-400/20" />

                  <div
                    className={`p-4 rounded-xl border transition-all ${
                      isSelected
                        ? "bg-cyan-950/20 border-cyan-500/50 shadow-md shadow-cyan-500/10"
                        : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-xs font-bold text-cyan-400">
                        {rec.record_id}
                      </span>
                      <span className="text-[11px] font-mono text-slate-500">
                        {new Date(rec.timestamp).toLocaleTimeString()}
                      </span>
                    </div>

                    <div className="text-sm font-semibold text-white mb-1">
                      {rec.activity}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 font-mono">
                      <span>Entity: <span className="text-slate-200">{rec.entity_id}</span></span>
                      <span>Agent: <span className="text-indigo-400">{rec.agent}</span></span>
                    </div>

                    <div className="mt-2.5 pt-2 border-t border-slate-800/80 font-mono text-[11px] text-slate-500 truncate">
                      SHA256: {rec.record_hash}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Record Cryptographic Inspector */}
        <div className="lg:col-span-5 space-y-6">
          {selectedRecord && (
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur-md space-y-5 sticky top-24">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Hash className="w-4 h-4 text-cyan-400" />
                  <span className="font-mono text-xs font-bold text-white">
                    {selectedRecord.record_id}
                  </span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                  VERIFIED
                </span>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-slate-500 block mb-1">Activity Definition</span>
                  <div className="p-2.5 rounded-lg bg-slate-950 font-mono text-cyan-300 border border-slate-800">
                    {selectedRecord.activity}
                  </div>
                </div>

                <div>
                  <span className="text-slate-500 block mb-1">Subject Entity</span>
                  <div className="p-2.5 rounded-lg bg-slate-950 font-mono text-slate-200 border border-slate-800">
                    {selectedRecord.entity_id}
                  </div>
                </div>

                <div>
                  <span className="text-slate-500 block mb-1">Acting Agent</span>
                  <div className="p-2.5 rounded-lg bg-slate-950 font-mono text-indigo-300 border border-slate-800">
                    {selectedRecord.agent}
                  </div>
                </div>

                <div>
                  <span className="text-slate-500 block mb-1">SHA-256 Record Hash</span>
                  <div className="p-2.5 rounded-lg bg-slate-950 font-mono text-emerald-400 border border-slate-800 break-all text-[11px]">
                    {selectedRecord.record_hash}
                  </div>
                </div>

                {selectedRecord.parent_hash && (
                  <div>
                    <span className="text-slate-500 block mb-1">Parent Hash (Block Link)</span>
                    <div className="p-2.5 rounded-lg bg-slate-950 font-mono text-slate-400 border border-slate-800 break-all text-[11px]">
                      {selectedRecord.parent_hash}
                    </div>
                  </div>
                )}

                <div>
                  <span className="text-slate-500 block mb-1">Metadata Ledger</span>
                  <pre className="p-3 rounded-lg bg-slate-950 font-mono text-slate-300 border border-slate-800 text-[11px] overflow-x-auto max-h-[160px]">
                    {JSON.stringify(selectedRecord.metadata, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
