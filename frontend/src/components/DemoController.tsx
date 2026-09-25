// src/components/DemoController.tsx – 1-Click Demo Trigger Bar for live judge presentations
import React, { useState } from "react";
import { Zap, Heart, Activity, AlertOctagon, ShieldAlert, Check, Loader2 } from "lucide-react";
import { cn } from "../lib/utils";
import { playEmergencyChime } from "../lib/audioAlert";
import { enqueueVoiceAlert } from "../lib/voiceAlerts";
import type { Lang } from "../lib/i18n";

interface DemoControllerProps {
  onRefetchPatients: () => void;
  lang?: Lang;
}

export function DemoController({ onRefetchPatients, lang = "en" }: DemoControllerProps) {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<string | null>(null);

  const triggerEvent = async (endpoint: string, payload: any, actionName: string) => {
    setLoadingAction(actionName);
    // Play emergency sound immediately for any SOS / Fall / High HR / Low SpO2 emergency trigger
    if (endpoint === "sos" || actionName.includes("SOS") || actionName.includes("Fall") || actionName.includes("Spike") || actionName.includes("Low")) {
      playEmergencyChime();
    }
    try {
      // Relative path so this works wherever the app is served from, not
      // only on the machine the backend happens to run on.
      const res = await fetch(`/api/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setLastAction(`Triggered: ${actionName}`);
        setTimeout(() => onRefetchPatients(), 300);
      }
    } catch (err) {
      console.error("Demo trigger error:", err);
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="bg-slate-900 text-white p-3 rounded-2xl border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-3">
      {/* Label & Sound Test */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-amber-500/20 rounded-lg text-amber-400">
            <Zap className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <h4 className="text-xs font-bold tracking-tight">Judges Demo Controller</h4>
            <p className="text-[10px] text-slate-400">Instant REST Telemetry Trigger</p>
          </div>
        </div>

        {/* Dedicated Audio Sound Test Button */}
        <button
          type="button"
          onClick={() => {
            enqueueVoiceAlert(
              { priority: "CRITICAL", eventType: "SOS", patientId: "P001", bed: "101" },
              lang
            );
          }}
          className="tactile-button px-2.5 py-1 bg-cyan-950 hover:bg-cyan-900 border border-cyan-500/50 text-cyan-300 rounded-xl text-xs font-bold flex items-center gap-1 shadow-sm"
        >
          🔊 Sound Test
        </button>
      </div>

      {/* Trigger Buttons */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Normal */}
        <button
          disabled={!!loadingAction}
          onClick={() =>
            triggerEvent(
              "sensor",
              { device_id: "wrist_01", patient_id: "P001", heart_rate: 76, spo2: 98, fall: false, sos: false },
              "Normal Vitals"
            )
          }
          className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition border border-slate-700"
        >
          <Check className="w-3.5 h-3.5 text-emerald-400" /> Normal (76 BPM)
        </button>

        {/* High HR */}
        <button
          disabled={!!loadingAction}
          onClick={() =>
            triggerEvent(
              "sensor",
              { device_id: "wrist_01", patient_id: "P001", heart_rate: 142, spo2: 97, fall: false, sos: false },
              "High HR Spike"
            )
          }
          className="px-2.5 py-1.5 bg-amber-950/80 hover:bg-amber-900 text-amber-300 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition border border-amber-800"
        >
          <Heart className="w-3.5 h-3.5 text-amber-400" /> HR Spike (142 BPM)
        </button>

        {/* Low SpO2 */}
        <button
          disabled={!!loadingAction}
          onClick={() =>
            triggerEvent(
              "sensor",
              { device_id: "wrist_01", patient_id: "P001", heart_rate: 85, spo2: 84, fall: false, sos: false },
              "Low SpO2"
            )
          }
          className="px-2.5 py-1.5 bg-blue-950/80 hover:bg-blue-900 text-blue-300 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition border border-blue-800"
        >
          <Activity className="w-3.5 h-3.5 text-blue-400" /> Low SpO2 (84%)
        </button>

        {/* Fall */}
        <button
          disabled={!!loadingAction}
          onClick={() =>
            triggerEvent(
              "sensor",
              { device_id: "wrist_01", patient_id: "P001", heart_rate: 90, spo2: 96, fall: true, sos: false },
              "Fall Incident"
            )
          }
          className="px-2.5 py-1.5 bg-red-950/90 hover:bg-red-900 text-red-300 rounded-xl text-xs font-bold flex items-center gap-1.5 transition border border-red-800"
        >
          <AlertOctagon className="w-3.5 h-3.5 text-red-400" /> Fall Incident
        </button>

        {/* SOS */}
        <button
          disabled={!!loadingAction}
          onClick={() =>
            triggerEvent(
              "sos",
              { device_id: "scan_01", patient_id: "P001" },
              "SOS Emergency"
            )
          }
          className="px-2.5 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-extrabold flex items-center gap-1.5 transition shadow-lg shadow-red-900/50"
        >
          <ShieldAlert className="w-3.5 h-3.5" /> SOS Button
        </button>

        {/* AI Co-Pilot Vitals Crash */}
        <button
          disabled={!!loadingAction}
          onClick={() =>
            triggerEvent(
              "sensor",
              { device_id: "wrist_01", patient_id: "P001", heart_rate: 142, spo2: 84, fall: false, sos: false },
              "Vitals Crash (142 BPM + 84% SpO2)"
            )
          }
          className="px-2.5 py-1.5 bg-cyan-950 hover:bg-cyan-900 text-cyan-300 rounded-xl text-xs font-bold flex items-center gap-1.5 transition border border-cyan-500/40 shadow-lg shadow-cyan-950/40"
        >
          <Zap className="w-3.5 h-3.5 text-cyan-400" /> AI Co-Pilot Demo (142 BPM / 84%)
        </button>
      </div>

      {/* Status indicator */}
      {loadingAction && (
        <span className="text-xs text-amber-400 flex items-center gap-1 font-mono">
          <Loader2 className="w-3 h-3 animate-spin" /> Transmitting {loadingAction}...
        </span>
      )}
      {!loadingAction && lastAction && (
        <span className="text-[11px] text-emerald-400 font-mono">{lastAction}</span>
      )}
    </div>
  );
}
