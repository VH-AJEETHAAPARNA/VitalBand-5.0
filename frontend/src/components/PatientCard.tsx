// Patient card component — smooth entrance, hover physics & vitals transitions
import { useEffect, useState, useMemo } from "react";
import type { Patient } from "../lib/types";
import { Badge } from "./ui/Badge";
import { cn } from "../lib/utils";
import type { Lang } from "../lib/i18n";
import { t } from "../lib/i18n";
import { Heart, Activity, Wifi, WifiOff, AlertOctagon, User, ShieldAlert } from "lucide-react";

interface PatientCardProps {
  patient: Patient;
  lang: Lang;
  index?: number;
  onClick?: () => void;
}

// Smooth animated number hook
function useAnimatedNumber(targetVal: number | undefined): string {
  const [displayVal, setDisplayVal] = useState<number>(0);

  useEffect(() => {
    if (targetVal == null) return;

    let start = displayVal || Math.max(0, targetVal - 15);
    let end = targetVal;
    let duration = 600; // ms
    let startTime: number | null = null;

    const step = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);
      // Ease out quad
      const current = Math.floor(start + (end - start) * (1 - (1 - progress) * (1 - progress)));
      setDisplayVal(current);
      if (progress < 1) {
        requestAnimationFrame(step);
      }
    };

    requestAnimationFrame(step);
  }, [targetVal]);

  return targetVal != null ? String(displayVal) : "--";
}

// Dynamic SVG Path generator from numerical array
function generateSvgPath(data: number[], width: number = 100, height: number = 30): string {
  if (!data || data.length < 2) {
    return `M0 ${height / 2} L${width} ${height / 2}`;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min === 0 ? 1 : max - min;

  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    // Invert Y so high numbers are higher up on screen
    const y = height - ((val - min) / range) * (height - 8) - 4;
    return `${x.toFixed(1)} ${y.toFixed(1)}`;
  });

  return `M ${points.join(" L ")}`;
}

export function PatientCard({ patient: p, lang, index = 0, onClick }: PatientCardProps) {
  const isAlert = p.fall || p.sos || p.distress || p.abnormal;
  const isCritical = p.fall || p.sos;

  const animatedHR = useAnimatedNumber(p.heart_rate);
  const animatedSpO2 = useAnimatedNumber(p.spo2);

  // Rolling history buffers for dynamic SVG sparklines
  const [hrHistory, setHrHistory] = useState<number[]>(() => [p.heart_rate ?? 75]);
  const [spo2History, setSpo2History] = useState<number[]>(() => [p.spo2 ?? 98]);

  useEffect(() => {
    if (p.heart_rate != null) {
      setHrHistory((prev) => [...prev.slice(-12), p.heart_rate!]);
    }
  }, [p.heart_rate]);

  useEffect(() => {
    if (p.spo2 != null) {
      setSpo2History((prev) => [...prev.slice(-12), p.spo2!]);
    }
  }, [p.spo2]);

  const hrSvgPath = useMemo(() => generateSvgPath(hrHistory), [hrHistory]);
  const spo2SvgPath = useMemo(() => generateSvgPath(spo2History), [spo2History]);

  // Stagger entrance delay calculation (cap at 400ms for safety)
  const staggerDelay = Math.min(index * 70, 420);

  return (
    <div
      onClick={onClick}
      style={{ animationDelay: `${staggerDelay}ms` }}
      className={cn(
        "group relative rounded-2xl border p-5 cursor-pointer tactile-button animate-card-entrance hover:scale-[1.02] hover:-translate-y-1 hover:shadow-xl bg-white/90 backdrop-blur-sm overflow-hidden transition-all duration-200",
        isCritical
          ? "border-red-500 bg-gradient-to-br from-red-50/90 via-white to-red-50/40 shadow-red-100 ring-2 ring-red-400/50"
          : isAlert
          ? "border-amber-400 bg-gradient-to-br from-amber-50/80 via-white to-white shadow-amber-100"
          : "border-gray-200/80 hover:border-slate-300 shadow-slate-100"
      )}
    >
      {/* Top accent bar for alerts (red reserved strictly for active alerts) */}
      {isAlert && (
        <div
          className={cn(
            "absolute top-0 left-0 right-0 h-1.5 transition-colors duration-200",
            isCritical ? "bg-[#d92b2b]" : "bg-amber-500"
          )}
        />
      )}

      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm shadow-inner transition-colors duration-200",
              isCritical
                ? "bg-red-100 text-red-700"
                : isAlert
                ? "bg-amber-100 text-amber-700"
                : "bg-slate-100 text-slate-700"
            )}
          >
            {p.name ? p.name.charAt(0) : <User className="w-5 h-5" />}
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-base tracking-tight leading-tight group-hover:text-[#0b2545] transition-colors">
              {p.name ?? `${t("patient", lang)} ${p.patient_id}`}
            </h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                ID: {p.patient_id}
              </span>
              {p.rfid_uid && (
                <span className="text-[10px] font-mono text-slate-500 bg-slate-50 border px-1.5 py-0.5 rounded">
                  RFID: {p.rfid_uid}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Connectivity Status */}
        <div className="flex items-center gap-1.5 bg-slate-50 p-1.5 rounded-lg border border-slate-100">
          <div
            title={p.wrist_connected ? "Wrist Patch Online" : "Wrist Offline"}
            className="flex items-center gap-1 text-[11px] font-medium"
          >
            {p.wrist_connected ? (
              <Wifi className="w-3.5 h-3.5 text-[#1e8e3e]" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-slate-300" />
            )}
          </div>
        </div>
      </div>

      {/* Vitals Cards with Live Sparklines */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {/* Heart Rate Sparkline Card */}
        <div
          className={cn(
            "flex items-center justify-between rounded-xl p-3 border transition-colors duration-200",
            p.abnormal || (p.heart_rate && (p.heart_rate > 100 || p.heart_rate < 55))
              ? "bg-slate-900/90 border-red-500/50 shadow-inner"
              : "bg-slate-900/80 border-slate-800"
          )}
        >
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
              {t("heartRate", lang) ?? "Heart Rate"}
            </span>
            <div className="text-xl font-bold text-white mt-0.5 font-mono">
              {animatedHR}{" "}
              <span
                className={cn(
                  "text-xs font-semibold",
                  p.abnormal || (p.heart_rate && (p.heart_rate > 100 || p.heart_rate < 55))
                    ? "text-red-400"
                    : "text-emerald-400"
                )}
              >
                BPM
              </span>
            </div>
          </div>

          {/* Dynamic Live Sparkline SVG */}
          <svg
            className={cn(
              "h-8 w-20 sm:w-24 shrink-0 transition-colors duration-200",
              p.abnormal || (p.heart_rate && (p.heart_rate > 100 || p.heart_rate < 55))
                ? "stroke-red-500 animate-pulse"
                : "stroke-emerald-400"
            )}
            fill="none"
            viewBox="0 0 100 30"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2.5"
              d={hrSvgPath}
            />
          </svg>
        </div>

        {/* SpO2 Sparkline Card */}
        <div
          className={cn(
            "flex items-center justify-between rounded-xl p-3 border transition-colors duration-200",
            p.abnormal || (p.spo2 && p.spo2 < 93)
              ? "bg-slate-900/90 border-red-500/50 shadow-inner"
              : "bg-slate-900/80 border-slate-800"
          )}
        >
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
              SpO2 Vitals
            </span>
            <div className="text-xl font-bold text-white mt-0.5 font-mono">
              {animatedSpO2}{" "}
              <span
                className={cn(
                  "text-xs font-semibold",
                  p.abnormal || (p.spo2 && p.spo2 < 93)
                    ? "text-red-400"
                    : "text-cyan-400"
                )}
              >
                %
              </span>
            </div>
          </div>

          {/* Dynamic Live SpO2 Sparkline SVG */}
          <svg
            className={cn(
              "h-8 w-20 sm:w-24 shrink-0 transition-colors duration-200",
              p.abnormal || (p.spo2 && p.spo2 < 93)
                ? "stroke-red-500 animate-pulse"
                : "stroke-cyan-400"
            )}
            fill="none"
            viewBox="0 0 100 30"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2.5"
              d={spo2SvgPath}
            />
          </svg>
        </div>
      </div>

      {/* Clinical Status Badges (smooth 150-200ms green->red transition) */}
      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        <Badge variant={p.fall ? "critical" : "ok"}>
          {p.fall ? (
            <span className="flex items-center gap-1">
              <AlertOctagon className="w-3 h-3 animate-spin" /> FALL DETECTED
            </span>
          ) : (
            "Fall: Normal"
          )}
        </Badge>
        <Badge variant={p.sos ? "critical" : "ok"}>
          {p.sos ? (
            <span className="flex items-center gap-1">
              <ShieldAlert className="w-3 h-3" /> SOS TRIGGERED
            </span>
          ) : (
            "SOS: OK"
          )}
        </Badge>
        {p.distress && (
          <Badge variant="warning">
            Facial Distress
          </Badge>
        )}
      </div>

      {/* Footer / Last sync */}
      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
        <span>Updated: {new Date(p.last_updated).toLocaleTimeString()}</span>
        <span className="text-[#0b2545] font-semibold group-hover:translate-x-1 transition-transform inline-flex items-center gap-1">
          Inspect Vitals →
        </span>
      </div>
    </div>
  );
}
