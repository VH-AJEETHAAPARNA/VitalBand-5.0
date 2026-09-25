// src/components/WardMapView.tsx
// Interactive SVG hospital floorplan — the "pre-admission gap" made visible.
//
// The layout is the pitch: the LEFT half is the waiting room (covered only by
// the rotating Scan Machine, no device on the patient), the RIGHT half is the
// admitted ward (covered by wristbands). The corridor between them is the gap
// VitalBand closes.
import React, { useMemo, useState } from "react";
import type { Patient } from "../lib/types";
import { getMEWSTriage } from "../lib/types";
import { Heart, Activity, MapPin, Radio, WifiOff, Filter } from "lucide-react";
import { cn } from "../lib/utils";
import { t, type Lang } from "../lib/i18n";

interface WardMapViewProps {
  patients: Patient[];
  onSelectPatient: (p: Patient) => void;
  privacyMode?: boolean;
  lang?: Lang;
}

type BedStatus = "critical" | "urgent" | "stable" | "offline" | "empty";
type FilterMode = "all" | "critical" | "empty";

interface BedSlot {
  id: string;
  label: string;
  patientId: string;
  x: number;
  y: number;
}

// Admitted ward: two rows of four beds.
const BED_W = 112;
const BED_H = 126;
const BEDS: BedSlot[] = [
  { id: "bed_101", label: "101", patientId: "P001", x: 508, y: 118 },
  { id: "bed_102", label: "102", patientId: "P002", x: 628, y: 118 },
  { id: "bed_103", label: "103", patientId: "P003", x: 748, y: 118 },
  { id: "bed_104", label: "104", patientId: "P004", x: 868, y: 118 },
  { id: "bed_105", label: "105", patientId: "P005", x: 508, y: 330 },
  { id: "bed_106", label: "106", patientId: "P006", x: 628, y: 330 },
  { id: "bed_107", label: "107", patientId: "P007", x: 748, y: 330 },
  { id: "bed_108", label: "108", patientId: "P008", x: 868, y: 330 },
];

// Waiting-room seats watched only by the Scan Machine camera.
const WAIT_SEATS = [
  { id: "wait_1", patientId: "P009", x: 88, y: 132 },
  { id: "wait_2", patientId: "P010", x: 168, y: 132 },
  { id: "wait_3", patientId: "P011", x: 88, y: 402 },
  { id: "wait_4", patientId: "P012", x: 168, y: 402 },
];

const SCAN_CX = 300;
const SCAN_CY = 288;

function statusOf(p: Patient | undefined): BedStatus {
  if (!p) return "empty";
  if (!p.wrist_connected && !p.scan_connected) return "offline";
  const triage = getMEWSTriage(p);
  if (triage.level === 1) return "critical";
  if (triage.level === 2) return "urgent";
  return "stable";
}

const PALETTE: Record<BedStatus, { fill: string; stroke: string; text: string; dot: string }> = {
  critical: { fill: "#450a0a", stroke: "#ef4444", text: "#fca5a5", dot: "#ef4444" },
  urgent:   { fill: "#451a03", stroke: "#f59e0b", text: "#fcd34d", dot: "#f59e0b" },
  stable:   { fill: "#052e2b", stroke: "#10b981", text: "#6ee7b7", dot: "#10b981" },
  offline:  { fill: "#1e293b", stroke: "#475569", text: "#94a3b8", dot: "#64748b" },
  empty:    { fill: "#0f172a", stroke: "#1e293b", text: "#475569", dot: "#334155" },
};

export function WardMapView({ patients, onSelectPatient, privacyMode, lang = "en" }: WardMapViewProps) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterMode>("all");

  const byId = useMemo(() => {
    const m = new Map<string, Patient>();
    for (const p of patients) m.set(p.patient_id, p);
    return m;
  }, [patients]);

  const criticalCount = useMemo(
    () => BEDS.filter((b) => statusOf(byId.get(b.patientId)) === "critical").length +
          WAIT_SEATS.filter((s) => statusOf(byId.get(s.patientId)) === "critical").length,
    [byId]
  );
  const emptyCount = useMemo(
    () => BEDS.filter((b) => !byId.get(b.patientId)).length,
    [byId]
  );

  // A slot is dimmed (not hidden) when filtered out, so the floorplan
  // never loses its spatial shape.
  const isDimmed = (status: BedStatus) => {
    if (filter === "all") return false;
    if (filter === "critical") return status !== "critical";
    return status !== "empty";
  };

  const displayName = (p: Patient) =>
    privacyMode ? `P-***${p.patient_id.slice(-1)}` : (p.name ?? `Patient ${p.patient_id}`);

  const hoveredSlot =
    BEDS.find((b) => b.id === hovered) ?? WAIT_SEATS.find((s) => s.id === hovered) ?? null;
  const hoveredPatient = hoveredSlot ? byId.get(hoveredSlot.patientId) : undefined;

  const FILTERS: { key: FilterMode; label: string; count?: number }[] = [
    { key: "all", label: t("allZones", lang) },
    { key: "critical", label: t("criticalEmergencies", lang), count: criticalCount },
    { key: "empty", label: t("unoccupied", lang), count: emptyCount },
  ];

  return (
    <div className="bg-slate-950 text-white rounded-3xl border border-slate-800 shadow-2xl overflow-hidden">
      {/* ── Control bar ── */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <MapPin className="w-5 h-5 text-cyan-400" />
            <h3 className="text-lg font-bold tracking-tight">{t("wardFloorplan", lang)}</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">{t("wardSubtitle", lang)}</p>
        </div>

        <div className="flex items-center gap-1.5 bg-slate-900 p-1 rounded-2xl border border-slate-800">
          <Filter className="w-3.5 h-3.5 text-slate-500 ml-1.5" />
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={cn(
                "tactile-button px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5",
                filter === f.key
                  ? "bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              )}
            >
              {f.label}
              {f.count !== undefined && (
                <span
                  className={cn(
                    "px-1.5 rounded-md text-[10px] font-mono",
                    filter === f.key ? "bg-slate-950/25" : "bg-slate-800"
                  )}
                >
                  {f.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Floorplan ── */}
      <div className="relative">
        <svg viewBox="0 0 1000 560" className="w-full h-auto block" role="img"
             aria-label="Interactive hospital ward floorplan showing waiting room and admitted ward beds">
          <defs>
            {/* Grey diagonal stripes = hardware offline */}
            <pattern id="vb-offline" width="8" height="8" patternTransform="rotate(45)"
                     patternUnits="userSpaceOnUse">
              <rect width="8" height="8" fill="#1e293b" />
              <line x1="0" y1="0" x2="0" y2="8" stroke="#475569" strokeWidth="3" />
            </pattern>
            {/* Sonar cone gradient */}
            <radialGradient id="vb-sonar" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="vb-gap" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.05" />
              <stop offset="50%" stopColor="#22d3ee" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.05" />
            </linearGradient>
            <filter id="vb-glow" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="5" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          <rect width="1000" height="560" fill="#020617" />

          {/* Floor grid */}
          <g opacity="0.25">
            {Array.from({ length: 25 }, (_, i) => (
              <line key={`v${i}`} x1={i * 40} y1="0" x2={i * 40} y2="560" stroke="#1e293b" strokeWidth="1" />
            ))}
            {Array.from({ length: 14 }, (_, i) => (
              <line key={`h${i}`} x1="0" y1={i * 40} x2="1000" y2={i * 40} stroke="#1e293b" strokeWidth="1" />
            ))}
          </g>

          {/* ── Waiting room shell ── */}
          <rect x="30" y="58" width="410" height="462" rx="18"
                fill="#0b2545" fillOpacity="0.55" stroke="#1e3a5f" strokeWidth="2" />
          <text x="50" y="86" fill="#7dd3fc" fontSize="13" fontWeight="700"
                letterSpacing="1.5" fontFamily="ui-sans-serif, system-ui">
            {t("waitingRoomZone", lang)}
          </text>
          <text x="50" y="104" fill="#475569" fontSize="10" fontFamily="ui-monospace, monospace">
            {t("noWearable", lang)}
          </text>

          {/* ── Admitted ward shell ── */}
          <rect x="478" y="58" width="492" height="462" rx="18"
                fill="#052e2b" fillOpacity="0.4" stroke="#134e4a" strokeWidth="2" />
          <text x="498" y="86" fill="#6ee7b7" fontSize="13" fontWeight="700"
                letterSpacing="1.5" fontFamily="ui-sans-serif, system-ui">
            {t("admittedWardZone", lang)}
          </text>
          <text x="498" y="104" fill="#475569" fontSize="10" fontFamily="ui-monospace, monospace">
            {t("wristTelemetry", lang)}
          </text>

          {/* ── The gap corridor (the whole pitch, drawn) ── */}
          <rect x="440" y="58" width="38" height="462" fill="url(#vb-gap)" />
          <text x="459" y="300" fill="#22d3ee" fontSize="10" fontWeight="700"
                letterSpacing="3" textAnchor="middle" transform="rotate(-90 459 300)"
                fontFamily="ui-monospace, monospace">
            THE PRE-ADMISSION GAP
          </text>

          {/* ── Scan Machine with rotating sonar ── */}
          <g>
            <circle cx={SCAN_CX} cy={SCAN_CY} r="118" fill="none"
                    stroke="#22d3ee" strokeOpacity="0.12" strokeWidth="1" strokeDasharray="4 6" />
            <circle className="ward-sonar-ring" cx={SCAN_CX} cy={SCAN_CY} fill="none" stroke="#22d3ee" />
            <circle className="ward-sonar-ring ward-sonar-ring-2" cx={SCAN_CX} cy={SCAN_CY} fill="none" stroke="#22d3ee" />

            {/* Rotating detection cone = sequential zone coverage */}
            <g className="ward-sonar-cone" style={{ transformOrigin: `${SCAN_CX}px ${SCAN_CY}px` }}>
              <path d={`M ${SCAN_CX} ${SCAN_CY} L ${SCAN_CX + 118} ${SCAN_CY - 46} A 118 118 0 0 1 ${SCAN_CX + 118} ${SCAN_CY + 46} Z`}
                    fill="url(#vb-sonar)" />
              <line x1={SCAN_CX} y1={SCAN_CY} x2={SCAN_CX + 118} y2={SCAN_CY}
                    stroke="#22d3ee" strokeWidth="1.5" strokeOpacity="0.7" />
            </g>

            <circle cx={SCAN_CX} cy={SCAN_CY} r="22" fill="#0f172a" stroke="#22d3ee" strokeWidth="2" filter="url(#vb-glow)" />
            <circle cx={SCAN_CX} cy={SCAN_CY} r="8" fill="#22d3ee" />
            <text x={SCAN_CX} y={SCAN_CY + 42} fill="#22d3ee" fontSize="10" fontWeight="700"
                  textAnchor="middle" fontFamily="ui-monospace, monospace">
              SCAN MACHINE
            </text>
            <text x={SCAN_CX} y={SCAN_CY + 56} fill="#475569" fontSize="9"
                  textAnchor="middle" fontFamily="ui-monospace, monospace">
              C270 · 3–5m POSE
            </text>
          </g>

          {/* ── Waiting-room occupants ── */}
          {WAIT_SEATS.map((seat) => {
            const p = byId.get(seat.patientId);
            const status = statusOf(p);
            const c = PALETTE[status];
            const dim = isDimmed(status);

            return (
              <g key={seat.id}
                 onMouseEnter={() => setHovered(seat.id)}
                 onMouseLeave={() => setHovered(null)}
                 onClick={() => p && onSelectPatient(p)}
                 opacity={dim ? 0.18 : 1}
                 style={{ cursor: p ? "pointer" : "default", transition: "opacity 0.3s" }}>
                {status === "critical" && (
                  <circle className="ward-critical-ring" cx={seat.x} cy={seat.y} r="30"
                          fill="none" stroke="#ef4444" />
                )}
                <rect x={seat.x - 26} y={seat.y - 26} width="52" height="52" rx="12"
                      fill={status === "offline" ? "url(#vb-offline)" : c.fill}
                      stroke={c.stroke} strokeWidth="2" />
                <circle cx={seat.x} cy={seat.y - 6} r="7" fill={c.dot} />
                <path d={`M ${seat.x - 11} ${seat.y + 15} q 11 -14 22 0`} fill={c.dot} opacity="0.85" />
                <text x={seat.x} y={seat.y + 42} fill={c.text} fontSize="9" fontWeight="700"
                      textAnchor="middle" fontFamily="ui-monospace, monospace">
                  {p ? seat.patientId : "SEAT"}
                </text>
              </g>
            );
          })}

          {/* ── Ward beds ── */}
          {BEDS.map((bed) => {
            const p = byId.get(bed.patientId);
            const status = statusOf(p);
            const c = PALETTE[status];
            const dim = isDimmed(status);
            const cx = bed.x + BED_W / 2;

            return (
              <g key={bed.id}
                 onMouseEnter={() => setHovered(bed.id)}
                 onMouseLeave={() => setHovered(null)}
                 onClick={() => p && onSelectPatient(p)}
                 opacity={dim ? 0.18 : 1}
                 style={{ cursor: p ? "pointer" : "default", transition: "opacity 0.3s" }}>

                {/* Level 1 heartbeat ring */}
                {status === "critical" && (
                  <rect className="ward-critical-ring"
                        x={bed.x - 6} y={bed.y - 6} width={BED_W + 12} height={BED_H + 12}
                        rx="18" fill="none" stroke="#ef4444" />
                )}
                {/* Level 2 breathing glow */}
                {status === "urgent" && (
                  <rect className="ward-breath"
                        x={bed.x - 4} y={bed.y - 4} width={BED_W + 8} height={BED_H + 8}
                        rx="16" fill="none" stroke="#f59e0b" strokeWidth="2.5" />
                )}

                <rect x={bed.x} y={bed.y} width={BED_W} height={BED_H} rx="14"
                      fill={status === "offline" ? "url(#vb-offline)" : c.fill}
                      stroke={c.stroke} strokeWidth="2"
                      filter={status === "critical" ? "url(#vb-glow)" : undefined} />

                {/* Bed label */}
                <text x={bed.x + 12} y={bed.y + 22} fill={c.text} fontSize="14" fontWeight="800"
                      fontFamily="ui-monospace, monospace">
                  {bed.label}
                </text>

                {/* Pillow + mattress silhouette */}
                <rect x={bed.x + 10} y={bed.y + 32} width={BED_W - 20} height="30" rx="7"
                      fill={c.stroke} fillOpacity="0.14" />
                <circle cx={bed.x + 26} cy={bed.y + 47} r="8" fill={c.dot} fillOpacity="0.85" />

                {p ? (
                  <>
                    {/* Live ECG trace — faster when critical */}
                    <path
                      className={cn("ward-ecg", status === "critical" && "ward-ecg-critical")}
                      d={`M ${bed.x + 10} ${bed.y + 84}
                          h 16 l 6 -13 l 7 26 l 6 -13 h 14
                          l 6 -9 l 6 18 l 5 -9 h 20`}
                      fill="none" stroke={c.stroke} strokeWidth="1.8"
                      strokeLinecap="round" strokeLinejoin="round" />

                    <text x={bed.x + 12} y={bed.y + 108} fill={c.text} fontSize="11" fontWeight="700"
                          fontFamily="ui-monospace, monospace">
                      {p.heart_rate ?? "--"}
                      <tspan fontSize="8" fillOpacity="0.7"> BPM</tspan>
                    </text>
                    <text x={bed.x + BED_W - 12} y={bed.y + 108} fill={c.text} fontSize="11" fontWeight="700"
                          textAnchor="end" fontFamily="ui-monospace, monospace">
                      {p.spo2 != null ? `${p.spo2}%` : "--"}
                    </text>
                  </>
                ) : (
                  <text x={cx} y={bed.y + 95} fill="#475569" fontSize="10"
                        textAnchor="middle" fontFamily="ui-monospace, monospace">
                    {t("unoccupied", lang)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* ── Hover tooltip (HTML overlay, positioned off the SVG viewBox) ── */}
        {hoveredSlot && (
          <div
            className="pointer-events-none absolute z-20 w-56 rounded-2xl border border-cyan-500/50 bg-slate-900/97 p-3 shadow-2xl backdrop-blur-md"
            style={{
              left: `${(hoveredSlot.x / 1000) * 100}%`,
              top: `${(hoveredSlot.y / 560) * 100}%`,
              transform: "translate(-50%, -115%)",
            }}
          >
            {hoveredPatient ? (
              <>
                <div className="flex items-center gap-2.5 mb-2.5">
                  {/* Patient photo placeholder */}
                  <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                    <span className="text-xs font-black text-slate-500 font-mono">
                      {hoveredPatient.patient_id.slice(-2)}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-white truncate">
                      {displayName(hoveredPatient)}
                    </p>
                    <p className="text-[10px] text-slate-400 font-mono">
                      {hoveredPatient.patient_id}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-1.5 mb-2">
                  <div className="bg-slate-950/70 rounded-lg p-1.5 border border-slate-800">
                    <span className="text-[9px] text-slate-500 flex items-center gap-1">
                      <Heart className="w-2.5 h-2.5 text-pink-500" /> HR
                    </span>
                    <span className="text-xs font-bold font-mono text-white">
                      {hoveredPatient.heart_rate ?? "--"}
                    </span>
                  </div>
                  <div className="bg-slate-950/70 rounded-lg p-1.5 border border-slate-800">
                    <span className="text-[9px] text-slate-500 flex items-center gap-1">
                      <Activity className="w-2.5 h-2.5 text-cyan-400" /> SpO₂
                    </span>
                    <span className="text-xs font-bold font-mono text-white">
                      {hoveredPatient.spo2 != null ? `${hoveredPatient.spo2}%` : "--"}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] border-t border-slate-800 pt-1.5">
                  <span className="text-slate-500 font-mono">
                    RFID {hoveredPatient.rfid_uid ?? "UNLINKED"}
                  </span>
                  {hoveredPatient.wrist_connected || hoveredPatient.scan_connected ? (
                    <span className="text-emerald-400 font-bold flex items-center gap-1">
                      <Radio className="w-2.5 h-2.5" /> {t("linked", lang)}
                    </span>
                  ) : (
                    <span className="text-slate-500 font-bold flex items-center gap-1">
                      <WifiOff className="w-2.5 h-2.5" /> {t("offline", lang)}
                    </span>
                  )}
                </div>
              </>
            ) : (
              <p className="text-xs text-slate-400 text-center py-1">
                {t("readyCheckin", lang)}
              </p>
            )}
          </div>
        )}
      </div>

      {/* ── Legend ── */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-6 py-3.5 border-t border-slate-800 text-[11px] font-medium text-slate-400">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-md bg-red-500" /> {t("legendL1", lang)}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-md bg-amber-500" /> {t("legendL2", lang)}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-md bg-emerald-500" /> {t("legendL3", lang)}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-md bg-slate-600" /> {t("legendOffline", lang)}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-md border border-slate-700 bg-slate-900" /> {t("legendEmpty", lang)}
        </span>
      </div>
    </div>
  );
}
