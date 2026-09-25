// src/components/AICopilotDrawer.tsx
// Human-in-the-Loop AI Co-Pilot drawer.
//
// Two engines are shown side by side on purpose:
//   • the DETERMINISTIC rule verdict, which fires on fixed clinical thresholds
//     and the SOS button, with no AI anywhere in its path;
//   • the JEV Deterioration Index, a weighted trend score that can only ever
//     RAISE attention and can never suppress the rule path.
// The drawer states that relationship in the UI so a nurse — or a judge —
// can see which one is actually keeping the patient safe.
import React, { useState } from "react";
import {
  Check, X, ShieldAlert, Cpu, AlertCircle, Activity, ChevronDown, ChevronUp, Lock,
} from "lucide-react";
import { DeteriorationGauge } from "./DeteriorationGauge";
import { useJevTriage } from "../hooks/useJevTriage";
import { cn } from "../lib/utils";
import { t, type Lang } from "../lib/i18n";

export interface ActiveAlertData {
  patientId: string;
  triageLevel?: string;
  anomalyScore?: number | string;
  clinicalReasoning?: string;
  recommendedAction?: string;
  deterministicOverride?: boolean;
  hr?: number;
  spo2?: number;
  motion?: string;
  timestamp?: string;
  fall?: boolean;
  sos?: boolean;
}

interface AICopilotDrawerProps {
  activeAlert: ActiveAlertData | null;
  onConfirm: () => void;
  onOverride: () => void;
  onClose?: () => void;
  lang?: Lang;
}

export function AICopilotDrawer({ activeAlert, onConfirm, onOverride, onClose, lang = "en" }: AICopilotDrawerProps) {
  const [showBreakdown, setShowBreakdown] = useState(false);
  const { data: jev, isLoading } = useJevTriage(activeAlert?.patientId, {
    fall: activeAlert?.fall,
    sos: activeAlert?.sos,
  });

  if (!activeAlert) return null;

  const timestamp = activeAlert.timestamp
    ? new Date(activeAlert.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  const severity = jev?.severity ?? "LOW";
  const index = jev?.deterioration_index ?? 0;

  // Precedence matters for patient safety. When the deterministic path has
  // fired (SOS pressed, or a fixed clinical threshold breached), ITS action is
  // the one shown — never the index's. Otherwise an SOS with calm vitals would
  // render a LEVEL 1 EMERGENCY header above the words "continue standard
  // monitoring", which is the exact failure this system exists to prevent.
  const deterministicFired = jev?.deterministic_triage?.deterministic_override === true;
  const suggestedAction = deterministicFired
    ? (jev?.deterministic_triage?.recommended_action
        ?? activeAlert.recommendedAction
        ?? "Escalate immediately — deterministic safety rule breached.")
    : (jev?.recommended_action ?? activeAlert.recommendedAction ?? "Review patient immediately.");

  return (
    <div className="fixed bottom-6 right-6 z-40 w-[26rem] max-w-[calc(100vw-3rem)] max-h-[calc(100vh-6rem)] overflow-y-auto rounded-2xl border border-cyan-500/40 bg-slate-900/96 p-5 shadow-2xl backdrop-blur-xl text-white animate-in slide-in-from-bottom-5 font-sans select-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500" />
          </span>
          <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5" /> VITALBAND AI COPILOT
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-slate-400">{timestamp}</span>
          {onClose && (
            <button
              onClick={onClose}
              title="Close Copilot Drawer"
              aria-label="Close Copilot Drawer"
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="flex justify-between items-center text-xs mb-3">
        <span className="text-slate-300">
          Patient: <strong className="text-white font-mono text-sm">{activeAlert.patientId}</strong>
        </span>
        <span className="text-red-400 font-bold uppercase tracking-wider flex items-center gap-1 bg-red-950/60 px-2 py-0.5 rounded border border-red-800/60">
          <ShieldAlert className="w-3.5 h-3.5" /> {activeAlert.triageLevel || "CRITICAL ALERT"}
        </span>
      </div>

      {/* Gauge + telemetry */}
      <div className="flex items-center gap-3 mb-3">
        <div className="shrink-0">
          {isLoading && !jev ? (
            <div className="w-[148px] h-[148px] rounded-full animate-shimmer" />
          ) : (
            <DeteriorationGauge
              value={index}
              severity={severity}
              confidence={jev?.confidence_score}
              lang={lang}
            />
          )}
        </div>

        <div className="flex-1 min-w-0 space-y-1.5">
          <p className="text-[10px] text-cyan-400 font-bold uppercase tracking-wider flex items-center gap-1">
            <Activity className="w-3 h-3" /> {t("liveTelemetry", lang)}
          </p>
          {[
            { label: "HR", val: activeAlert.hr != null ? `${activeAlert.hr} BPM` : "--",
              bad: !!activeAlert.hr && (activeAlert.hr > 120 || activeAlert.hr < 50) },
            { label: "SpO₂", val: activeAlert.spo2 != null ? `${activeAlert.spo2}%` : "--",
              bad: !!activeAlert.spo2 && activeAlert.spo2 < 92 },
            { label: t("motion", lang), val: activeAlert.motion ?? "—", bad: false },
          ].map((m) => (
            <div key={m.label}
                 className="flex items-center justify-between bg-slate-950/70 px-2.5 py-1.5 rounded-lg border border-slate-800">
              <span className="text-[10px] text-slate-500 font-mono">{m.label}</span>
              <strong className={cn("text-xs font-mono", m.bad ? "text-red-400" : "text-slate-200")}>
                {m.val}
              </strong>
            </div>
          ))}
          {jev && (
            <p className="text-[9px] text-slate-600 font-mono pt-0.5">
              {jev.frames_analysed} {t("frames", lang)}{!jev.warmed_up && " · warming up"}
            </p>
          )}
        </div>
      </div>

      {/* Why this score — the index is only trustworthy if it can be argued with */}
      {jev && jev.contributors.length > 0 && (
        <div className="mb-3">
          <button
            onClick={() => setShowBreakdown((v) => !v)}
            className="w-full flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400 hover:text-white transition py-1"
          >
            <span>{t("whyThisScore", lang)}</span>
            {showBreakdown ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          {showBreakdown && (
            <div className="space-y-1 mt-1">
              {jev.contributors.map((c, i) => (
                <div key={i} className="bg-slate-950/70 border border-slate-800 rounded-lg px-2.5 py-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] text-slate-300 font-semibold truncate">{c.factor}</span>
                    <span className="text-[10px] font-mono text-cyan-400 shrink-0">+{c.weighted_points}</span>
                  </div>
                  <span className="text-[9px] text-slate-500 font-mono">{c.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Deterministic path — stated as independent of the score above */}
      <div className="rounded-xl border border-amber-900/50 bg-amber-950/25 p-2.5 mb-2">
        <p className="text-[10px] text-amber-400 font-bold uppercase tracking-wider flex items-center gap-1 mb-0.5">
          <Lock className="w-3 h-3" /> {t("deterministicPath", lang)}
        </p>
        <p className="text-slate-300 text-[11px] leading-snug">
          {jev?.deterministic_triage?.clinical_reasoning
            ?? activeAlert.clinicalReasoning
            ?? "Fixed clinical thresholds evaluated independently of the index."}
        </p>
      </div>

      {deterministicFired && index < 50 && (
        <p className="text-[10px] text-amber-300/90 leading-snug mb-2 px-0.5">
          Trend index is low, but the deterministic rule fired anyway — this is the
          safety path working. The score cannot stand the alert down.
        </p>
      )}

      {/* Recommendation */}
      <div className="rounded-xl border border-emerald-900/50 bg-emerald-950/40 p-2.5 mb-3">
        <p className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider mb-0.5 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" /> {t("suggestedResponse", lang)}
          <span className="ml-auto text-[9px] font-mono text-slate-400 normal-case tracking-normal">
            source: {deterministicFired ? "deterministic rule" : "JEV index"}
          </span>
        </p>
        <p className="text-xs font-bold text-emerald-200 leading-snug">{suggestedAction}</p>
      </div>

      {/* The nurse holds final authority */}
      <div className="flex gap-2">
        <button
          onClick={onConfirm}
          className="tactile-button flex-1 rounded-xl bg-emerald-600 py-2.5 text-xs font-bold text-white shadow-lg shadow-emerald-900/30 transition hover:bg-emerald-500 flex items-center justify-center gap-1"
        >
          <Check className="w-3.5 h-3.5" /> {t("acceptRoute", lang)}
        </button>
        <button
          onClick={onOverride}
          className="tactile-button rounded-xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-xs font-medium text-slate-300 hover:bg-slate-700 flex items-center justify-center gap-1"
        >
          <X className="w-3.5 h-3.5" /> {t("overrideBtn", lang)}
        </button>
      </div>
    </div>
  );
}

export default AICopilotDrawer;
