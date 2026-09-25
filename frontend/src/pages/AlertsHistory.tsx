// src/pages/AlertsHistory.tsx – enhanced: animated row slide-flash, severity filters, search & CSV export
import React, { useState, useMemo } from "react";
import { useAlertHistory } from "../hooks/useAlerts";
import { t, type Lang } from "../lib/i18n";
import type { AlertEvent } from "../lib/types";
import { Loader2, Search, Download, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "../lib/utils";

interface AlertsHistoryProps {
  lang: Lang;
}

const PAGE_SIZE = 20;

const SEVERITY_TABS = ["ALL", "CRITICAL", "WARNING", "INFO"] as const;
type SeverityFilter = typeof SEVERITY_TABS[number];

const DATE_RANGES = [
  { label: "Today",      days: 0 },
  { label: "Last 7d",   days: 7 },
  { label: "Last 30d",  days: 30 },
  { label: "All time",  days: -1 },
] as const;

function SeverityBadge({ severity }: { severity: string }) {
  const cls = {
    CRITICAL: "bg-red-100 text-[#d92b2b] border border-red-200 font-bold",
    WARNING:  "bg-amber-100 text-amber-700 border border-amber-200 font-semibold",
    INFO:     "bg-gray-100 text-gray-500 border border-gray-200 font-medium",
  }[severity] ?? "bg-gray-100 text-gray-500";
  return <span className={cn("px-2 py-0.5 rounded text-xs", cls)}>{severity}</span>;
}

function exportCSV(rows: AlertEvent[]) {
  const header = "id,patient_id,event_type,severity,details,timestamp";
  const lines = rows.map((r) =>
    [r.id, r.patient_id, r.event_type, r.severity, `"${r.details ?? ""}"`, r.timestamp].join(",")
  );
  const blob = new Blob([[header, ...lines].join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "vitalband_history.csv"; a.click();
  URL.revokeObjectURL(url);
}

export function AlertsHistory({ lang }: AlertsHistoryProps) {
  const { data: alerts, isLoading, error } = useAlertHistory();

  const [severity, setSeverity]     = useState<SeverityFilter>("ALL");
  const [dateRange, setDateRange]   = useState<number>(7);     // days, -1 = all
  const [search, setSearch]         = useState("");
  const [page, setPage]             = useState(0);

  const filtered = useMemo(() => {
    if (!alerts) return [];
    const cutoff = dateRange >= 0
      ? Date.now() - (dateRange === 0 ? 0 : dateRange * 24 * 60 * 60 * 1000)
      : 0;
    const startOfToday = new Date(); startOfToday.setHours(0, 0, 0, 0);

    return alerts.filter((a) => {
      const ts = new Date(a.timestamp).getTime();
      const matchDate = dateRange === -1 ? true
        : dateRange === 0 ? ts >= startOfToday.getTime()
        : ts >= cutoff;
      const matchSev = severity === "ALL" || a.severity === severity;
      const q = search.toLowerCase();
      const matchQ = !q
        || a.patient_id.toLowerCase().includes(q)
        || a.event_type.toLowerCase().includes(q)
        || (a.details ?? "").toLowerCase().includes(q);
      return matchDate && matchSev && matchQ;
    });
  }, [alerts, severity, dateRange, search]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated  = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const resetPage = () => setPage(0);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-[#0b2545]" />
        <span className="ml-2 text-gray-600">{t("loading", lang) ?? "Loading…"}</span>
      </div>
    );
  }

  if (error) {
    return <div className="p-4 text-[#d92b2b]">Error loading alert history.</div>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-gray-800">Alert History</h1>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-center justify-between">
        {/* Severity filter pills */}
        <div className="flex gap-1.5 flex-wrap">
          {SEVERITY_TABS.map((s) => (
            <button
              key={s}
              onClick={() => { setSeverity(s); resetPage(); }}
              className={cn(
                "tactile-button px-3 py-1 rounded-full text-xs font-medium border transition-colors",
                severity === s
                  ? s === "CRITICAL" ? "bg-[#d92b2b] text-white border-[#d92b2b]"
                    : s === "WARNING" ? "bg-amber-500 text-white border-amber-500"
                    : s === "INFO" ? "bg-gray-600 text-white border-gray-600"
                    : "bg-[#0b2545] text-white border-[#0b2545]"
                  : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
              )}
            >{s}</button>
          ))}
        </div>

        {/* Date range + search + export */}
        <div className="flex gap-2 items-center flex-wrap">
          <div className="flex gap-1 border rounded-lg overflow-hidden text-xs">
            {DATE_RANGES.map((d) => (
              <button
                key={d.label}
                onClick={() => { setDateRange(d.days); resetPage(); }}
                className={cn(
                  "tactile-button px-3 py-1.5 font-medium transition-colors",
                  dateRange === d.days
                    ? "bg-[#0b2545] text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                )}
              >{d.label}</button>
            ))}
          </div>
          <div className="relative">
            <Search className="absolute left-2 top-2 w-4 h-4 text-gray-400" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); resetPage(); }}
              placeholder="Search…"
              className="pl-8 pr-3 py-1.5 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300 w-44"
            />
          </div>
          <button
            onClick={() => exportCSV(filtered)}
            className="tactile-button flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Download className="w-4 h-4" /> Export CSV
          </button>
        </div>
      </div>

      {/* Results count */}
      <p className="text-xs text-gray-400">{filtered.length} events matching filters</p>

      {/* Table with Slide-In Flash Rows */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <table className="min-w-full">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wider">
            <tr>
              {["#","Timestamp","Patient ID","Event","Severity","Details"].map((h) => (
                <th key={h} className="px-4 py-2 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {paginated.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-gray-400 text-sm">
                  No alerts match your filters.
                </td>
              </tr>
            ) : paginated.map((a, idx) => (
              <tr
                key={a.id}
                style={{ animationDelay: `${idx * 40}ms` }}
                className={cn(
                  "animate-row-slide-flash transition-colors hover:bg-gray-50",
                  a.severity === "CRITICAL" && "bg-red-50/80"
                )}
              >
                <td className="px-4 py-2 text-xs text-gray-400 font-mono">{a.id}</td>
                <td className="px-4 py-2 text-xs text-gray-500 whitespace-nowrap">
                  {new Date(a.timestamp).toLocaleString()}
                </td>
                <td className="px-4 py-2 text-sm font-mono font-medium">{a.patient_id}</td>
                <td className="px-4 py-2 text-sm font-medium">{a.event_type.replace(/_/g, " ")}</td>
                <td className="px-4 py-2"><SeverityBadge severity={a.severity} /></td>
                <td className="px-4 py-2 text-xs text-gray-500 max-w-xs truncate" title={a.details ?? ""}>
                  {a.details ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>Page {page + 1} of {totalPages}</span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage(p => p - 1)}
              className="tactile-button p-1.5 rounded border disabled:opacity-40 hover:bg-gray-100"
            ><ChevronLeft className="w-4 h-4" /></button>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage(p => p + 1)}
              className="tactile-button p-1.5 rounded border disabled:opacity-40 hover:bg-gray-100"
            ><ChevronRight className="w-4 h-4" /></button>
          </div>
        </div>
      )}
    </div>
  );
}
