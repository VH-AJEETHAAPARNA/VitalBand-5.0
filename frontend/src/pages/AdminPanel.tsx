// src/pages/AdminPanel.tsx – tabbed admin console: Fleet Overview, Alert Log, Device Fleet
import React, { useState, useMemo } from "react";
import { usePatients } from "../hooks/usePatients";
import { useAlertHistory } from "../hooks/useAlerts";
import { PatientDetailModal } from "../components/PatientDetailModal";
import { t, type Lang } from "../lib/i18n";
import type { Patient, AlertEvent } from "../lib/types";
import {
  Loader2, Activity, Wifi, AlertTriangle, Monitor,
  Download, Search, ChevronLeft, ChevronRight, Brain, Cpu
} from "lucide-react";
import { MLOpsPanel } from "../components/MLOpsPanel";
import { AIStackPanel } from "../components/AIStackPanel";
import { cn } from "../lib/utils";

// ─────────────────────── helpers ────────────────────────────────────────────

function SeverityBadge({ severity }: { severity: string }) {
  const cls = {
    CRITICAL: "bg-red-100 text-red-700 border border-red-200",
    WARNING:  "bg-amber-100 text-amber-700 border border-amber-200",
    INFO:     "bg-gray-100 text-gray-600 border border-gray-200",
  }[severity] ?? "bg-gray-100 text-gray-600";
  return <span className={cn("px-2 py-0.5 rounded text-xs font-medium", cls)}>{severity}</span>;
}

function exportCSV(rows: AlertEvent[], filename: string) {
  const header = "id,patient_id,event_type,severity,details,timestamp";
  const lines = rows.map((r) =>
    [r.id, r.patient_id, r.event_type, r.severity, `"${r.details ?? ""}"`, r.timestamp].join(",")
  );
  const blob = new Blob([[header, ...lines].join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ─────────────────────── Tab: Fleet Overview ────────────────────────────────

function FleetOverview({
  patients,
  alerts,
  lang,
}: {
  patients: Patient[];
  alerts: AlertEvent[];
  lang: Lang;
}) {
  const [selected, setSelected] = useState<Patient | null>(null);

  const criticalCount = alerts.filter((a) => a.severity === "CRITICAL").length;
  const wristConnected = patients.filter((p) => p.wrist_connected).length;
  const scanConnected  = patients.filter((p) => p.scan_connected).length;

  const stats = [
    { label: "Total Patients",    value: patients.length,  icon: <Activity className="w-5 h-5 text-blue-500" /> },
    { label: "Wrist Connected",   value: wristConnected,   icon: <Wifi className="w-5 h-5 text-green-500" /> },
    { label: "Scanner Connected", value: scanConnected,    icon: <Monitor className="w-5 h-5 text-purple-500" /> },
    { label: "Critical Alerts",   value: criticalCount,    icon: <AlertTriangle className="w-5 h-5 text-red-500" /> },
  ];

  return (
    <div className="space-y-6">
      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-white rounded-xl shadow-sm border p-4 flex items-center gap-3">
            {s.icon}
            <div>
              <p className="text-xs text-gray-500">{s.label}</p>
              <p className="text-2xl font-bold text-gray-800">{s.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Live patient table */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div className="px-4 py-3 border-b">
          <h3 className="font-semibold text-gray-800">Live Patient Fleet</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
              <tr>
                {["Patient ID","Name","HR","SpO2","Fall","SOS","Last Updated",""].map((h) => (
                  <th key={h} className="px-4 py-2 text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {patients.map((p) => {
                const isCritical = p.fall_status !== "NORMAL" || p.sos_status !== "NORMAL";
                return (
                  <tr
                    key={p.patient_id}
                    className={cn(
                      "hover:bg-gray-50 cursor-pointer transition-colors",
                      isCritical && "bg-red-50 hover:bg-red-100"
                    )}
                    onClick={() => setSelected(p)}
                  >
                    <td className="px-4 py-2 text-sm font-mono">{p.patient_id}</td>
                    <td className="px-4 py-2 text-sm">{p.name ?? "—"}</td>
                    <td className="px-4 py-2 text-sm font-semibold">{p.heart_rate ?? "—"}</td>
                    <td className="px-4 py-2 text-sm font-semibold">{p.spo2 != null ? `${p.spo2}%` : "—"}</td>
                    <td className="px-4 py-2 text-sm">
                      {p.fall_status !== "NORMAL"
                        ? <span className="text-red-600 font-bold">⚠ FALL</span>
                        : <span className="text-green-600">OK</span>}
                    </td>
                    <td className="px-4 py-2 text-sm">
                      {p.sos_status !== "NORMAL"
                        ? <span className="text-red-600 font-bold">🆘 SOS</span>
                        : <span className="text-green-600">OK</span>}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-400">
                      {new Date(p.last_updated).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-2 text-xs text-blue-500 hover:underline">Details →</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <PatientDetailModal patient={selected} onClose={() => setSelected(null)} lang={lang} />
      )}
    </div>
  );
}

// ─────────────────────── Tab: Alert Log ─────────────────────────────────────

const PAGE_SIZE = 20;

function AlertLog({ alerts }: { alerts: AlertEvent[] }) {
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState<"ALL" | "CRITICAL" | "WARNING" | "INFO">("ALL");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    return alerts.filter((a) => {
      const matchSev = severity === "ALL" || a.severity === severity;
      const q = search.toLowerCase();
      const matchQ = !q || a.patient_id.toLowerCase().includes(q) || a.event_type.toLowerCase().includes(q);
      return matchSev && matchQ;
    });
  }, [alerts, search, severity]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const SEVS = ["ALL", "CRITICAL", "WARNING", "INFO"] as const;

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-center justify-between">
        <div className="flex gap-2">
          {SEVS.map((s) => (
            <button
              key={s}
              onClick={() => { setSeverity(s); setPage(0); }}
              className={cn(
                "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                severity === s
                  ? s === "CRITICAL" ? "bg-red-600 text-white border-red-600"
                    : s === "WARNING" ? "bg-amber-500 text-white border-amber-500"
                    : s === "INFO" ? "bg-gray-600 text-white border-gray-600"
                    : "bg-[#0b2545] text-white border-[#0b2545]"
                  : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
              )}
            >{s}</button>
          ))}
        </div>
        <div className="flex gap-2 items-center">
          <div className="relative">
            <Search className="absolute left-2 top-2 w-4 h-4 text-gray-400" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
              placeholder="Search patient / event…"
              className="pl-8 pr-3 py-1.5 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
          </div>
          <button
            onClick={() => exportCSV(filtered, "vitalband_alerts.csv")}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Download className="w-4 h-4" /> Export CSV
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <table className="min-w-full">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
            <tr>
              {["#","Timestamp","Patient ID","Event Type","Severity","Details"].map((h) => (
                <th key={h} className="px-4 py-2 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {paginated.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm">No alerts found</td></tr>
            ) : paginated.map((a) => (
              <tr key={a.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-xs text-gray-400">{a.id}</td>
                <td className="px-4 py-2 text-xs text-gray-500 whitespace-nowrap">{new Date(a.timestamp).toLocaleString()}</td>
                <td className="px-4 py-2 text-sm font-mono">{a.patient_id}</td>
                <td className="px-4 py-2 text-sm">{a.event_type}</td>
                <td className="px-4 py-2"><SeverityBadge severity={a.severity} /></td>
                <td className="px-4 py-2 text-xs text-gray-500 max-w-xs truncate">{a.details ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>{filtered.length} total · page {page + 1} of {totalPages}</span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage(p => p - 1)}
              className="p-1 rounded border disabled:opacity-40 hover:bg-gray-100"
            ><ChevronLeft className="w-4 h-4" /></button>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage(p => p + 1)}
              className="p-1 rounded border disabled:opacity-40 hover:bg-gray-100"
            ><ChevronRight className="w-4 h-4" /></button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────── Tab: Device Fleet ──────────────────────────────────

function DeviceFleet({ patients }: { patients: Patient[] }) {
  type DeviceRow = { device_id: string; type: string; patient_id: string; last_seen: string; connected: boolean };

  const devices: DeviceRow[] = useMemo(() => {
    const rows: DeviceRow[] = [];
    patients.forEach((p) => {
      if (p.device_id) {
        rows.push({
          device_id: p.device_id,
          type: p.device_id.startsWith("scan") ? "Scan Machine" : "Wrist Patch",
          patient_id: p.patient_id,
          last_seen: p.last_updated,
          connected: Boolean(p.wrist_connected || p.scan_connected),
        });
      }
    });
    return rows;
  }, [patients]);

  return (
    <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <h3 className="font-semibold text-gray-800">Registered Devices ({devices.length})</h3>
      </div>
      <table className="min-w-full">
        <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
          <tr>
            {["Device ID","Type","Patient","Last Seen","Status"].map((h) => (
              <th key={h} className="px-4 py-2 text-left">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {devices.length === 0 ? (
            <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400 text-sm">No devices registered yet. Start the simulator or connect hardware.</td></tr>
          ) : devices.map((d) => (
            <tr key={d.device_id} className="hover:bg-gray-50">
              <td className="px-4 py-2 text-sm font-mono">{d.device_id}</td>
              <td className="px-4 py-2 text-sm">{d.type}</td>
              <td className="px-4 py-2 text-sm font-mono">{d.patient_id}</td>
              <td className="px-4 py-2 text-xs text-gray-400 whitespace-nowrap">{new Date(d.last_seen).toLocaleString()}</td>
              <td className="px-4 py-2">
                <span className={cn(
                  "px-2 py-0.5 rounded-full text-xs font-medium",
                  d.connected ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                )}>
                  {d.connected ? "● Online" : "○ Offline"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─────────────────────── Main Component ─────────────────────────────────────

type Tab = "fleet" | "alerts" | "devices" | "mlops" | "aistack";

export function AdminPanel({ lang }: { lang: Lang }) {
  const [activeTab, setActiveTab] = useState<Tab>("fleet");
  const { data: patients, isLoading: pLoad } = usePatients();
  const { data: history, isLoading: hLoad } = useAlertHistory();

  if (pLoad || hLoad) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-[#0b2545]" />
        <span className="ml-2 text-gray-600">Loading admin data…</span>
      </div>
    );
  }

  const safePatients = patients ?? [];
  const safeHistory  = history  ?? [];

  const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "fleet",   label: "Fleet Overview", icon: <Activity className="w-4 h-4" /> },
    { id: "alerts",  label: "Alert Log",      icon: <AlertTriangle className="w-4 h-4" /> },
    { id: "devices", label: "Device Fleet",   icon: <Monitor className="w-4 h-4" /> },
    { id: "mlops",   label: "Model Training",  icon: <Brain className="w-4 h-4" /> },
    { id: "aistack", label: "AI Stack",        icon: <Cpu className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-gray-800">Admin Console</h1>

      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors",
              activeTab === tab.id
                ? "border-[#0b2545] text-[#0b2545]"
                : "border-transparent text-gray-500 hover:text-gray-700"
            )}
          >
            {tab.icon}{tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "fleet"   && <FleetOverview patients={safePatients} alerts={safeHistory} lang={lang} />}
      {activeTab === "alerts"  && <AlertLog alerts={safeHistory} />}
      {activeTab === "devices" && <DeviceFleet patients={safePatients} />}
      {activeTab === "mlops"   && <MLOpsPanel />}
      {activeTab === "aistack" && <AIStackPanel />}
    </div>
  );
}
