// src/components/IntroSplashScreen.tsx
// Landing page.
//
// The motion here narrates the product rather than decorating it: an ECG line
// draws itself and a pulse rides it (the signal we watch), a scan bar sweeps
// the hero (the rotating Scan Machine), and the alert ring uses the same
// double-beat rhythm as a critical bed on the dashboard — so the landing page
// and the product speak one visual language.
//
// Everything is CSS-driven and respects prefers-reduced-motion via the global
// rule in index.css.
import React, { useEffect, useState } from "react";
import {
  Activity, ShieldCheck, ArrowRight, Zap, Radio, Languages, Cpu,
} from "lucide-react";

interface IntroSplashScreenProps {
  onProceedToLogin: (fillRole?: "nurse" | "admin") => void;
}

const HEADLINE = ["Closing", "the", "pre-admission", "gap."];

const STATS = [
  { value: "1:836", label: "Doctor to patient ratio in India" },
  { value: "~₹2,000", label: "Per patient, all-in" },
  { value: "4", label: "Languages spoken to nurses" },
];

const PILLARS = [
  {
    icon: <Radio className="w-4 h-4" />,
    title: "Scan Machine",
    body: "Watches the waiting room from the second someone arrives — no device on the patient.",
  },
  {
    icon: <Activity className="w-4 h-4" />,
    title: "Wrist Patch",
    body: "MAX30102 heart rate and SpO₂ once admitted, posted every five seconds.",
  },
  {
    icon: <ShieldCheck className="w-4 h-4" />,
    title: "Deterministic alerts",
    body: "The SOS button and clinical thresholds fire without asking any model for permission.",
  },
];

export function IntroSplashScreen({ onProceedToLogin }: IntroSplashScreenProps) {
  // Gate the entrance animations until after mount so they always play.
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setReady(true), 30);
    return () => clearTimeout(t);
  }, []);

  const delay = (ms: number): React.CSSProperties =>
    ready ? { animationDelay: `${ms}ms` } : { animationPlayState: "paused" };

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-[#050F1F] text-white select-none">
      {/* ── depth: drifting aurora blooms ── */}
      <div className="pointer-events-none absolute inset-0">
        <div className="aurora absolute -top-40 -left-32 h-[34rem] w-[34rem] rounded-full bg-cyan-500/18 blur-[130px]" />
        <div className="aurora-slow absolute top-1/3 -right-40 h-[38rem] w-[38rem] rounded-full bg-emerald-500/14 blur-[140px]" />
        <div className="aurora absolute -bottom-52 left-1/3 h-[30rem] w-[30rem] rounded-full bg-blue-600/16 blur-[130px]" />
      </div>

      {/* ── floorplan grid, drifting slowly ── */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden opacity-[0.35]">
        <div
          className="grid-drift absolute inset-x-0 -top-14 h-[calc(100%+4rem)]"
          style={{
            backgroundImage:
              "linear-gradient(to right, rgba(56,189,248,0.07) 1px, transparent 1px)," +
              "linear-gradient(to bottom, rgba(56,189,248,0.07) 1px, transparent 1px)",
            backgroundSize: "56px 56px",
          }}
        />
      </div>

      {/* ── the Scan Machine sweep ── */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="hero-sweep absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-cyan-300/10 to-transparent" />
      </div>

      {/* ── ECG trace across the hero ── */}
      <svg
        className="pointer-events-none absolute left-0 right-0 top-[46%] h-40 w-full opacity-70"
        viewBox="0 0 1400 160"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          className="hero-ecg"
          d="M0,80 H240 l18,-34 l14,74 l16,-40 h60 l14,-18 l14,36 l12,-18 H700
             l20,-56 l16,108 l18,-52 h70 l16,-22 l14,44 l12,-22 H1400"
          fill="none"
          stroke="rgba(34,211,238,0.85)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      {/* ── content ── */}
      <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8">
        {/* top bar */}
        <div className="rise flex items-center justify-between" style={delay(0)}>
          <div className="flex items-center gap-3">
            <span className="relative grid h-11 w-11 place-items-center rounded-2xl border border-cyan-400/30 bg-cyan-500/10">
              <span className="heart-ring absolute inset-0 rounded-2xl border border-cyan-400/50" />
              <Activity className="h-5 w-5 text-cyan-300" />
            </span>
            <div>
              <p className="text-base font-black tracking-tight">VITALBAND</p>
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-cyan-400/80">
                Clinical safety platform
              </p>
            </div>
          </div>

          <span className="hidden items-center gap-2 rounded-full border border-white/12 bg-white/5 px-3.5 py-1.5 text-[11px] font-semibold text-white/80 backdrop-blur sm:flex">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
            DPDP Act 2023 aligned
          </span>
        </div>

        {/* hero */}
        <div className="my-auto max-w-4xl py-10">
          <p
            className="rise mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-400/25 bg-cyan-500/10 px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-cyan-300"
            style={delay(120)}
          >
            <Zap className="h-3.5 w-3.5" />
            Human-AI Collaboration
          </p>

          <h1 className="text-5xl font-black leading-[1.05] tracking-tight sm:text-7xl">
            {HEADLINE.map((w, i) => (
              <span
                key={w}
                className="word mr-[0.28em]"
                style={ready ? { animationDelay: `${220 + i * 110}ms` } : { animationPlayState: "paused" }}
              >
                {w === "pre-admission" ? (
                  <span className="bg-gradient-to-r from-cyan-300 via-teal-200 to-emerald-300 bg-clip-text text-transparent">
                    {w}
                  </span>
                ) : (
                  w
                )}
              </span>
            ))}
          </h1>

          <p className="rise mt-6 max-w-2xl text-base leading-relaxed text-white/70 sm:text-lg" style={delay(700)}>
            A patient can sit in a hospital waiting room and deteriorate in full view of everyone —
            too weak to speak, or simply unnoticed. VitalBand watches that gap, and raises the alarm
            before anyone has to collapse to be seen.
          </p>

          {/* stats */}
          <div className="mt-10 grid max-w-2xl grid-cols-3 gap-5">
            {STATS.map((s, i) => (
              <div key={s.label} className="stat-land" style={delay(860 + i * 120)}>
                <p className="text-2xl font-black tracking-tight text-white sm:text-3xl">{s.value}</p>
                <p className="mt-1 text-[11px] leading-snug text-white/55">{s.label}</p>
              </div>
            ))}
          </div>

          {/* CTA */}
          <div className="rise mt-11 flex flex-wrap items-center gap-3" style={delay(1240)}>
            <button
              onClick={() => onProceedToLogin()}
              className="tactile-button group relative inline-flex items-center gap-2.5 overflow-hidden rounded-2xl bg-white px-7 py-3.5 text-sm font-extrabold tracking-wide text-[#050F1F] shadow-2xl shadow-cyan-500/10 transition hover:shadow-cyan-400/25"
            >
              <span className="cta-sheen pointer-events-none absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-white/60 to-transparent" />
              ENTER CLINICAL CONSOLE
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </button>

            <button
              onClick={() => onProceedToLogin("nurse")}
              className="tactile-button rounded-2xl border border-white/15 bg-white/5 px-5 py-3.5 text-sm font-bold text-white/85 backdrop-blur transition hover:bg-white/10"
            >
              Nurse demo
            </button>
            <button
              onClick={() => onProceedToLogin("admin")}
              className="tactile-button rounded-2xl border border-white/15 bg-white/5 px-5 py-3.5 text-sm font-bold text-white/85 backdrop-blur transition hover:bg-white/10"
            >
              Admin demo
            </button>
          </div>
        </div>

        {/* pillars */}
        <div className="grid gap-4 pb-6 sm:grid-cols-3">
          {PILLARS.map((p, i) => (
            <div
              key={p.title}
              className="rise group rounded-2xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur transition hover:border-cyan-400/30 hover:bg-white/[0.07]"
              style={delay(1420 + i * 130)}
            >
              <span className="mb-3 inline-grid h-9 w-9 place-items-center rounded-xl border border-cyan-400/25 bg-cyan-500/10 text-cyan-300">
                {p.icon}
              </span>
              <p className="text-sm font-bold">{p.title}</p>
              <p className="mt-1.5 text-xs leading-relaxed text-white/60">{p.body}</p>
            </div>
          ))}
        </div>

        {/* footer */}
        <div
          className="rise flex flex-col items-start justify-between gap-2 border-t border-white/10 pt-4 text-[11px] text-white/45 sm:flex-row sm:items-center"
          style={delay(1820)}
        >
          <span>Team InstantZero · Chennai Institute of Technology</span>
          <span className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <Languages className="h-3.5 w-3.5" /> Tamil · Hindi · Kannada · English
            </span>
            <span className="flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5" /> Rules decide · AI explains
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}
