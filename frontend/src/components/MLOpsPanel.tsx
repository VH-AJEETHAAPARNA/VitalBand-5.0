// src/components/MLOpsPanel.tsx
// Continuous-retraining console for the secondary anomaly baseline.
//
// The panel leads with the safety boundary rather than burying it, because
// "the AI retrains itself" is exactly the claim a clinical reviewer should
// push back on. Retraining only ever tunes the statistical signal; the
// deterministic thresholds and the SOS path are never touched.
import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Brain, RefreshCw, RotateCcw, Loader2, ShieldCheck,
  TrendingUp, AlertTriangle, CheckCircle2, Database,
} from "lucide-react";
import { cn } from "../lib/utils";

interface ModelRun {
  version: number;
  status: string;
  trigger: string;
  trained_on_rows: number;
  created_at: string;
  notes?: string | null;
  params: Record<string, number | boolean>;
  metrics: Record<string, any>;
}

interface MLOpsStatus {
  active: ModelRun | null;
  using_defaults: boolean;
  retrain_every_n_readings: number;
  readings_since_last_retrain: number;
  min_rows_to_train: number;
  safety_note: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
  return res.json();
}

async function postJSON<T>(path: string): Promise<T> {
  const res = await fetch(path, { method: "POST" });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
  return res.json();
}

function Stat({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "good" | "warn" }) {
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
      <p className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">{label}</p>
      <p className={cn(
        "text-sm font-bold font-mono mt-0.5",
        tone === "good" ? "text-emerald-600" : tone === "warn" ? "text-amber-600" : "text-gray-800"
      )}>
        {value}
      </p>
    </div>
  );
}

export function MLOpsPanel() {
  const qc = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const { data: status, isLoading: sLoad } = useQuery<MLOpsStatus>({
    queryKey: ["mlops-status"],
    queryFn: () => getJSON<MLOpsStatus>("/api/mlops/status"),
    refetchInterval: 5000,
  });

  const { data: runs, isLoading: rLoad } = useQuery<ModelRun[]>({
    queryKey: ["mlops-runs"],
    queryFn: () => getJSON<ModelRun[]>("/api/mlops/runs?limit=15"),
    refetchInterval: 5000,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["mlops-status"] });
    qc.invalidateQueries({ queryKey: ["mlops-runs"] });
  };

  const retrain = useMutation({
    mutationFn: () => postJSON<ModelRun>("/api/mlops/retrain"),
    onSuccess: (m) => { setMessage({ kind: "ok", text: `Trained v${m.version} on ${m.trained_on_rows} readings.` }); invalidate(); },
    onError: (e: Error) => setMessage({ kind: "err", text: e.message }),
  });

  const rollback = useMutation({
    mutationFn: (v: number) => postJSON<ModelRun>(`/api/mlops/rollback/${v}`),
    onSuccess: (m) => { setMessage({ kind: "ok", text: `Rolled back — now serving v${m.version}.` }); invalidate(); },
    onError: (e: Error) => setMessage({ kind: "err", text: e.message }),
  });

  if (sLoad || rLoad) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-[#0b2545]" />
        <span className="ml-2 text-gray-600">Loading model registry…</span>
      </div>
    );
  }

  const active = status?.active ?? null;
  const pending = status?.readings_since_last_retrain ?? 0;
  const every = status?.retrain_every_n_readings ?? 50;
  const pct = Math.min(100, (pending / every) * 100);
  // A model trained before this field existed reports nothing — treat that as
  // "unknown", not "failing". Only warn when calibration explicitly failed.
  const calibration = active?.metrics?.calibration_healthy;
  const healthy = calibration === true;
  const calibrationUnknown = calibration === undefined;

  return (
    <div className="space-y-5">
      {/* Safety boundary — stated first, not buried */}
      <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl p-3.5">
        <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-xs font-bold text-blue-900">Retraining Safety Boundary</h4>
          <p className="text-xs text-blue-800/90 mt-0.5">
            {status?.safety_note ??
              "Retraining tunes only the secondary statistical signal. Deterministic clinical thresholds and the SOS path are never modified."}
          </p>
        </div>
      </div>

      {message && (
        <div className={cn(
          "rounded-xl px-3.5 py-2.5 text-xs font-semibold flex items-center gap-2 border",
          message.kind === "ok"
            ? "bg-emerald-50 border-emerald-200 text-emerald-800"
            : "bg-red-50 border-red-200 text-red-800"
        )}>
          {message.kind === "ok" ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
          {message.text}
        </div>
      )}

      {/* Active model */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div className="px-4 py-3 border-b flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-[#0b2545]" />
            <h3 className="text-sm font-bold text-gray-800">Active Baseline Model</h3>
            {active ? (
              <span className="px-2 py-0.5 rounded-md bg-[#0b2545] text-white text-[10px] font-bold font-mono">
                v{active.version}
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded-md bg-gray-200 text-gray-700 text-[10px] font-bold">
                FACTORY DEFAULTS
              </span>
            )}
          </div>

          <button
            onClick={() => retrain.mutate()}
            disabled={retrain.isPending}
            className="tactile-button flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0b2545] text-white text-xs font-bold hover:bg-slate-800 transition disabled:opacity-50"
          >
            {retrain.isPending
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <RefreshCw className="w-3.5 h-3.5" />}
            RETRAIN NOW
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Auto-retrain progress */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-gray-600 font-medium flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-gray-400" />
                Next automatic retrain
              </span>
              <span className="font-mono text-gray-500">{pending} / {every} readings</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-blue-600 transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {active ? (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <Stat label="Trained on" value={`${active.trained_on_rows} rows`} />
                <Stat
                  label="Warning band"
                  value={`|z| ≥ ${active.params.z_warning}`}
                />
                <Stat
                  label="Flag rate"
                  value={`${((active.metrics.warning_rate ?? 0) * 100).toFixed(1)}%`}
                  tone={calibrationUnknown ? "default" : healthy ? "good" : "warn"}
                />
                <Stat
                  label="Pop. drift"
                  value={`${active.metrics?.drift?.max_shift ?? 0}σ`}
                  tone={active.metrics?.drift?.significant ? "warn" : "default"}
                />
              </div>

              {/* Calibration honesty — do not present a clamped model as fine */}
              {!healthy && !calibrationUnknown && (
                <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl p-3">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div className="text-xs text-amber-900">
                    <strong>Calibration target not met.</strong>{" "}
                    {active.metrics?.calibration_clamped
                      ? "The fitted threshold exceeded a clinical safety bound and was clamped, so this model flags more often than intended."
                      : "This model's flag rate is above target and may be noisy."}{" "}
                    Consider rolling back to a healthier version below.
                  </div>
                </div>
              )}

              {active.notes && (
                <p className="text-xs text-gray-500 leading-relaxed">{active.notes}</p>
              )}
            </>
          ) : (
            <p className="text-xs text-gray-500">
              No model trained yet — the scorer is using its factory thresholds.
              At least {status?.min_rows_to_train ?? 30} stored readings are needed to train.
            </p>
          )}
        </div>
      </div>

      {/* Run history */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div className="px-4 py-3 border-b flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-[#0b2545]" />
          <h3 className="text-sm font-bold text-gray-800">Training Run History</h3>
          <span className="text-[11px] text-gray-400 ml-auto">append-only · newest first</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-gray-50 text-gray-500 uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 font-bold">Version</th>
                <th className="px-3 py-2 font-bold">Trigger</th>
                <th className="px-3 py-2 font-bold">Rows</th>
                <th className="px-3 py-2 font-bold">|z| warn</th>
                <th className="px-3 py-2 font-bold">Flag rate</th>
                <th className="px-3 py-2 font-bold">Drift</th>
                <th className="px-3 py-2 font-bold">Trained</th>
                <th className="px-3 py-2 font-bold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {(runs ?? []).length === 0 ? (
                <tr><td colSpan={8} className="px-3 py-8 text-center text-gray-400">No training runs yet.</td></tr>
              ) : (
                (runs ?? []).map((r) => {
                  const isActive = r.status === "active";
                  const cal = r.metrics?.calibration_healthy;
                  const ok = cal === true;
                  const unknown = cal === undefined;
                  return (
                    <tr key={r.version} className={cn(isActive && "bg-blue-50/60")}>
                      <td className="px-3 py-2 font-mono font-bold text-gray-800">
                        v{r.version}
                        {isActive && (
                          <span className="ml-1.5 px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 text-[9px] font-bold">
                            ACTIVE
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] font-bold",
                          r.trigger === "auto" ? "bg-cyan-100 text-cyan-700"
                            : r.trigger === "rollback" ? "bg-purple-100 text-purple-700"
                            : "bg-gray-100 text-gray-600"
                        )}>
                          {r.trigger}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono text-gray-600">{r.trained_on_rows}</td>
                      <td className="px-3 py-2 font-mono text-gray-600">{String(r.params?.z_warning ?? "—")}</td>
                      <td className={cn(
                        "px-3 py-2 font-mono font-semibold",
                        unknown ? "text-gray-600" : ok ? "text-emerald-600" : "text-amber-600"
                      )}>
                        {((r.metrics?.warning_rate ?? 0) * 100).toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 font-mono text-gray-600">
                        {r.metrics?.drift?.max_shift ?? 0}σ
                      </td>
                      <td className="px-3 py-2 text-gray-500 whitespace-nowrap">
                        {new Date(r.created_at).toLocaleTimeString()}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {!isActive && (
                          <button
                            onClick={() => rollback.mutate(r.version)}
                            disabled={rollback.isPending}
                            className="tactile-button inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-gray-300 text-gray-700 text-[11px] font-bold hover:bg-gray-50 transition disabled:opacity-50"
                          >
                            <RotateCcw className="w-3 h-3" /> Roll back
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
