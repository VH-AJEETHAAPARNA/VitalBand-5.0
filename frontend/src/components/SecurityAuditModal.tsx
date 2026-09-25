// src/components/SecurityAuditModal.tsx
// DPDP Act 2023 governance panel + tamper-evident audit trail.
import React, { useEffect, useState } from "react";
import {
  ShieldCheck, EyeOff, CheckCircle2, X, Download, Link2, AlertTriangle, Loader2,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { cn } from "../lib/utils";
import {
  subscribeAudit, recordAudit, verifyChain, exportAuditCsv, type AuditEntry,
} from "../lib/auditLog";

interface SecurityAuditModalProps {
  onClose: () => void;
  privacyMode: boolean;
  onTogglePrivacy: () => void;
}

const EVENT_STYLES: Record<string, string> = {
  AUTH_LOGIN: "bg-cyan-950 text-cyan-300 border-cyan-800",
  PRIVACY_MASK_TOGGLED: "bg-indigo-950 text-indigo-300 border-indigo-800",
  ALERT_ACKNOWLEDGED: "bg-emerald-950 text-emerald-300 border-emerald-800",
  AI_RECOMMENDATION_OVERRIDDEN: "bg-amber-950 text-amber-300 border-amber-800",
  VITALS_OVERRIDE: "bg-amber-950 text-amber-300 border-amber-800",
  PATIENT_RECORD_VIEWED: "bg-slate-800 text-slate-300 border-slate-700",
  PATIENT_RFID_CHECKOUT: "bg-blue-950 text-blue-300 border-blue-800",
  AUDIT_EXPORTED: "bg-purple-950 text-purple-300 border-purple-800",
};

export function SecurityAuditModal({ onClose, privacyMode, onTogglePrivacy }: SecurityAuditModalProps) {
  const { user } = useAuth();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [verifying, setVerifying] = useState(false);
  const [verdict, setVerdict] = useState<{ ok: boolean; brokenAt: number | null } | null>(null);

  useEffect(() => subscribeAudit(setEntries), []);

  const actor = {
    actorId: user?.email ?? "unknown",
    actorRole: user?.role ?? "nurse",
  };

  const handleTogglePrivacy = () => {
    onTogglePrivacy();
    void recordAudit({
      ...actor,
      eventType: "PRIVACY_MASK_TOGGLED",
      subject: "ALL_PATIENTS",
      detail: `Privacy mask turned ${privacyMode ? "OFF" : "ON"}`,
    });
  };

  const handleVerify = async () => {
    setVerifying(true);
    setVerdict(null);
    const res = await verifyChain();
    setVerdict(res);
    setVerifying(false);
  };

  const handleExport = async () => {
    await recordAudit({
      ...actor,
      eventType: "AUDIT_EXPORTED",
      subject: `${entries.length} ROWS`,
      detail: "Encrypted audit CSV exported",
    });
    exportAuditCsv();
  };

  const COMPLIANCE_ITEMS = [
    { title: "DPDP Act 2023 — Data Minimisation", status: "COMPLIANT", detail: "Only vitals required for triage are retained; no free-text PII in telemetry." },
    { title: "Transport Encryption (TLS 1.3)", status: "ACTIVE", detail: "Device → backend REST and WebSocket channels are TLS-terminated." },
    { title: "Role-Based Access Control", status: "ENFORCED", detail: `Session: ${user?.full_name ?? "User"} (${user?.role ?? "nurse"}) — admin routes gated.` },
    { title: "Multi-Tenant Hospital Isolation", status: "ISOLATED", detail: `Every query scoped to tenant ${user?.hospital_id ?? "DEFAULT_HOSP"}.` },
    { title: "Deterministic Emergency Override", status: "VERIFIED", detail: "SOS and clinical thresholds bypass the ML path entirely — AI cannot suppress an alert." },
  ];

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/75 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="bg-slate-950 rounded-3xl shadow-2xl border border-slate-800 max-w-4xl w-full overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="bg-[#0b2545] text-white px-6 py-5 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-cyan-500/15 rounded-2xl border border-cyan-400/30">
              <ShieldCheck className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight">Security &amp; DPDP Privacy Audit</h2>
              <p className="text-xs text-blue-200/80 mt-0.5">Compliance posture and tamper-evident access log</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl text-white/70 hover:text-white hover:bg-white/10 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-6">
          {/* Privacy mask */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-indigo-600 text-white rounded-xl shadow-md shrink-0">
                <EyeOff className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-bold text-white text-sm">Public Presentation Privacy Mask</h4>
                <p className="text-xs text-slate-400 mt-0.5">
                  Replaces every patient name and ID with <span className="font-mono text-slate-300">P-***1</span> across the whole UI.
                </p>
              </div>
            </div>
            <button
              onClick={handleTogglePrivacy}
              className={cn(
                "tactile-button px-4 py-2 rounded-xl text-xs font-bold transition shrink-0",
                privacyMode ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              )}
            >
              {privacyMode ? "MASK: ON" : "MASK: OFF"}
            </button>
          </div>

          {/* Controls */}
          <div>
            <h3 className="text-xs font-bold uppercase text-slate-500 tracking-wider mb-3">Active Security Controls</h3>
            <div className="grid gap-2.5">
              {COMPLIANCE_ITEMS.map((item, idx) => (
                <div key={idx} className="p-3.5 bg-slate-900 border border-slate-800 rounded-xl flex items-start gap-3">
                  <CheckCircle2 className="w-4.5 h-4.5 text-emerald-500 shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-3">
                      <h4 className="font-bold text-slate-100 text-xs">{item.title}</h4>
                      <span className="text-[10px] font-extrabold px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-md shrink-0">
                        {item.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{item.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Audit chain */}
          <div>
            <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
              <div>
                <h3 className="text-xs font-bold uppercase text-slate-500 tracking-wider flex items-center gap-1.5">
                  <Link2 className="w-3.5 h-3.5" /> Cryptographic Audit Trail
                </h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Append-only · each HMAC-SHA256 signs the row <em>and</em> its parent signature
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleVerify}
                  disabled={verifying || entries.length === 0}
                  className="tactile-button px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 text-xs font-bold hover:bg-slate-700 transition disabled:opacity-40 flex items-center gap-1.5"
                >
                  {verifying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                  VERIFY CHAIN
                </button>
                <button
                  onClick={handleExport}
                  disabled={entries.length === 0}
                  className="tactile-button px-3 py-2 rounded-xl bg-cyan-600 text-white text-xs font-bold hover:bg-cyan-500 transition disabled:opacity-40 flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" /> EXPORT AUDIT CSV
                </button>
              </div>
            </div>

            {verdict && (
              <div className={cn(
                "mb-3 rounded-xl px-3.5 py-2.5 text-xs font-bold flex items-center gap-2 border",
                verdict.ok
                  ? "bg-emerald-950/60 border-emerald-800 text-emerald-300"
                  : "bg-red-950/60 border-red-800 text-red-300"
              )}>
                {verdict.ok ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                {verdict.ok
                  ? `Chain intact — all ${entries.length} entries re-verified against their parent signature.`
                  : `TAMPER DETECTED — chain integrity fails at sequence #${verdict.brokenAt}.`}
              </div>
            )}

            <div className="rounded-2xl border border-slate-800 overflow-hidden">
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full text-left text-[11px]">
                  <thead className="bg-slate-900 sticky top-0">
                    <tr className="text-slate-500 uppercase tracking-wider">
                      <th className="px-3 py-2 font-bold">#</th>
                      <th className="px-3 py-2 font-bold">Timestamp</th>
                      <th className="px-3 py-2 font-bold">Actor</th>
                      <th className="px-3 py-2 font-bold">Event</th>
                      <th className="px-3 py-2 font-bold">Subject</th>
                      <th className="px-3 py-2 font-bold">HMAC-SHA256</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80">
                    {entries.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-3 py-8 text-center text-slate-500">
                          No audited actions in this session yet.
                        </td>
                      </tr>
                    ) : (
                      [...entries].reverse().map((e) => (
                        <tr key={e.seq} className="bg-slate-950 hover:bg-slate-900/70 transition">
                          <td className="px-3 py-2 font-mono text-slate-500">{e.seq}</td>
                          <td className="px-3 py-2 font-mono text-slate-400 whitespace-nowrap">
                            {new Date(e.timestamp).toLocaleTimeString()}
                          </td>
                          <td className="px-3 py-2 text-slate-300 whitespace-nowrap">
                            {e.actorId}
                            <span className="text-slate-600 ml-1">({e.actorRole})</span>
                          </td>
                          <td className="px-3 py-2">
                            <span className={cn(
                              "px-1.5 py-0.5 rounded border text-[10px] font-bold whitespace-nowrap",
                              EVENT_STYLES[e.eventType] ?? "bg-slate-800 text-slate-300 border-slate-700"
                            )}>
                              {e.eventType}
                            </span>
                          </td>
                          <td className="px-3 py-2 font-mono text-slate-400">{e.subject}</td>
                          <td className="px-3 py-2 font-mono text-cyan-500/80" title={e.signature}>
                            {e.signature.slice(0, 16)}…
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 bg-slate-900 border-t border-slate-800 flex items-center justify-between shrink-0">
          <span className="text-[11px] text-slate-500 font-mono">
            {entries.length} signed {entries.length === 1 ? "entry" : "entries"} · JWT HS256 session
          </span>
          <button
            onClick={onClose}
            className="tactile-button px-5 py-2.5 bg-slate-800 text-white font-bold text-xs rounded-xl hover:bg-slate-700 transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
