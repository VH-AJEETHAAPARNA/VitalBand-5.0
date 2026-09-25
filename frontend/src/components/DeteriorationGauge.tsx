// src/components/DeteriorationGauge.tsx
// Animated SVG gauge for the JEV Deterioration Index (0–100).
//
// The arc sweeps to its value and the readout counts up with it, so a rising
// index reads as movement rather than a number that silently changed. Colour
// is carried by the arc AND the severity label, never by hue alone.
import React, { useEffect, useRef, useState } from "react";
import { t, type Lang } from "../lib/i18n";

interface DeteriorationGaugeProps {
  value: number;              // 0–100
  severity: string;           // LOW | MODERATE | HIGH | CRITICAL
  confidence?: number;        // 0–1
  size?: number;
  lang?: Lang;
}

const RADIUS = 52;
const STROKE = 9;
// Open-bottom gauge: 270° of sweep starting from the lower-left.
const SWEEP = 270;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const ARC_LEN = CIRCUMFERENCE * (SWEEP / 360);

const SEVERITY_COLOR: Record<string, string> = {
  CRITICAL: "#ef4444",
  HIGH: "#f97316",
  MODERATE: "#f59e0b",
  LOW: "#10b981",
};

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const on = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

export function DeteriorationGauge({
  value,
  severity,
  confidence,
  size = 148,
  lang = "en",
}: DeteriorationGaugeProps) {
  const target = Math.max(0, Math.min(100, value));
  const reduced = usePrefersReducedMotion();
  const [shown, setShown] = useState(reduced ? target : 0);
  const rafRef = useRef<number | null>(null);
  const fromRef = useRef(0);

  // Ease the readout from wherever it was to the new target.
  useEffect(() => {
    if (reduced) {
      setShown(target);
      return;
    }
    const from = fromRef.current;
    const start = performance.now();
    const DURATION = 900;

    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / DURATION);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - p, 3);
      const next = from + (target - from) * eased;
      setShown(next);
      if (p < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = target;
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      fromRef.current = shown;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, reduced]);

  const color = SEVERITY_COLOR[severity] ?? "#64748b";
  const filled = ARC_LEN * (shown / 100);
  const cx = size / 2;
  const cy = size / 2;

  // 21 ticks around the sweep; the ones below the value light up.
  const ticks = Array.from({ length: 21 }, (_, i) => {
    const frac = i / 20;
    const angle = (135 + frac * SWEEP) * (Math.PI / 180);
    const inner = RADIUS - STROKE / 2 - 5;
    const outer = RADIUS - STROKE / 2 - 1;
    return {
      key: i,
      x1: cx + Math.cos(angle) * inner,
      y1: cy + Math.sin(angle) * inner,
      x2: cx + Math.cos(angle) * outer,
      y2: cy + Math.sin(angle) * outer,
      lit: frac * 100 <= shown,
    };
  });

  return (
    <div className="flex flex-col items-center" role="img"
         aria-label={`Deterioration index ${Math.round(target)} out of 100, severity ${severity}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <filter id="gauge-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Track */}
        <circle
          cx={cx} cy={cy} r={RADIUS}
          fill="none" stroke="#1e293b" strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={`${ARC_LEN} ${CIRCUMFERENCE}`}
          transform={`rotate(135 ${cx} ${cy})`}
        />

        {/* Value arc */}
        <circle
          cx={cx} cy={cy} r={RADIUS}
          fill="none" stroke={color} strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${CIRCUMFERENCE}`}
          transform={`rotate(135 ${cx} ${cy})`}
          filter={severity === "CRITICAL" ? "url(#gauge-glow)" : undefined}
        />

        {/* Scale ticks */}
        {ticks.map((tick) => (
          <line
            key={tick.key}
            x1={tick.x1} y1={tick.y1} x2={tick.x2} y2={tick.y2}
            stroke={tick.lit ? color : "#334155"}
            strokeWidth="1.5"
            strokeLinecap="round"
            opacity={tick.lit ? 0.9 : 0.4}
          />
        ))}

        {/* Readout */}
        <text
          x={cx} y={cy - 2}
          textAnchor="middle" dominantBaseline="middle"
          fill="#ffffff" fontSize="30" fontWeight="800"
          fontFamily="ui-monospace, monospace"
        >
          {Math.round(shown)}
        </text>
        <text
          x={cx} y={cy + 20}
          textAnchor="middle" fill="#64748b" fontSize="9"
          letterSpacing="1.5" fontFamily="ui-monospace, monospace"
        >
          / 100
        </text>
        <text
          x={cx} y={cy + 38}
          textAnchor="middle" fill={color} fontSize="10" fontWeight="800"
          letterSpacing="1.2" fontFamily="ui-sans-serif, system-ui"
        >
          {severity}
        </text>
      </svg>

      <p className="text-[10px] text-slate-500 font-mono -mt-1">
        {t("deteriorationIndex", lang)}
        {confidence != null && ` · ${Math.round(confidence * 100)}% conf`}
      </p>
    </div>
  );
}
