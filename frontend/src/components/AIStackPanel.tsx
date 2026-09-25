// src/components/AIStackPanel.tsx
// Honest status board for the AI stack.
//
// It deliberately shows what is NOT running as prominently as what is. Triton
// and self-hosted NIM need a local NVIDIA GPU; claiming them on a host without
// one is exactly the sort of thing that collapses under one question.
import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Cpu, ShieldCheck, Volume2, Zap, Loader2, CheckCircle2,
  MinusCircle, AlertTriangle, Send,
} from "lucide-react";
import { cn } from "../lib/utils";

interface ServiceStatus {
  service: string;
  configured: boolean;
  mode: string;
  role: string;
  detail: string;
  model?: string | null;
  checks?: string[];
  on_violation?: string;
}

interface AIStatus {
  deterministic_engine: ServiceStatus;
  nim: ServiceStatus;
  guardrails: ServiceStatus;
  riva: ServiceStatus;
  triton: ServiceStatus;
  host_has_nvidia_gpu: boolean;
  safety_note: string;
}

interface ExplainResult {
  triage_level: string;
  deterministic_override: boolean;
  explanation: string;
  source: string;
  guardrail_passed: boolean;
  guardrail_violations: string[];
}

const ICONS: Record<string, React.ReactNode> = {
  deterministic_engine: <ShieldCheck className="w-4 h-4" />,
  nim: <Cpu className="w-4 h-4" />,
  guardrails: <ShieldCheck className="w-4 h-4" />,
  riva: <Volume2 className="w-4 h-4" />,
  triton: <Zap className="w-4 h-4" />,
};

function ModeBadge({ mode }: { mode: string }) {
  const map: Record<string, string> = {
    active: "bg-emerald-100 text-emerald-700 border-emerald-200",
    hosted: "bg-emerald-100 text-emerald-700 border-emerald-200",
    fallback: "bg-amber-100 text-amber-700 border-amber-200",
    disabled: "bg-slate-100 text-slate-600 border-slate-200",
    unavailable: "bg-slate-100 text-slate-600 border-slate-200",
  };
  const icon =
    mode === "active" || mode === "hosted" ? <CheckCircle2 className="w-3 h-3" />
      : mode === "fallback" ? <AlertTriangle className="w-3 h-3" />
      : <MinusCircle className="w-3 h-3" />;
  return (
    <span className={cn(
      "px-2 py-0.5 rounded-md text-[10px] font-bold border flex items-center gap-1 shrink-0 uppercase",
      map[mode] ?? map.disabled
    )}>
      {icon}{mode}
    </span>
  );
}

export function AIStackPanel() {
  const { data, isLoading } = useQuery<AIStatus>({
    queryKey: ["ai-status"],
    queryFn: async () => {
      const r = await fetch("/api/ai/status");
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    },
    refetchInterval: 15000,
  });

  const [result, setResult] = useState<ExplainResult | null>(null);
  const [busy, setBusy] = useState(false);

  const runExplain = async () => {
    setBusy(true);
    setResult(null);
    try {
      const r = await fetch("/api/ai/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: "P007", heart_rate: 142, spo2: 84,
          deterioration_index: 80.5,
        }),
      });
      setResult(await r.json());
    } catch {
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-[#0b2545]" />
        <span className="ml-2 text-gray-600">Reading AI stack status…</span>
      </div>
    );
  }

  const rows: [string, ServiceStatus][] = [
    ["deterministic_engine", data.deterministic_engine],
    ["guardrails", data.guardrails],
    ["nim", data.nim],
    ["riva", data.riva],
    ["triton", data.triton],
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl p-3.5">
        <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-xs font-bold text-blue-900">Model authority</h4>
          <p className="text-xs text-blue-800/90 mt-0.5">{data.safety_note}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div className="px-4 py-3 border-b flex items-center justify-between">
          <h3 className="text-sm font-bold text-gray-800">AI Stack — live status</h3>
          <span className={cn(
            "text-[11px] font-bold px-2 py-0.5 rounded-md border",
            data.host_has_nvidia_gpu
              ? "bg-emerald-100 text-emerald-700 border-emerald-200"
              : "bg-slate-100 text-slate-600 border-slate-200"
          )}>
            {data.host_has_nvidia_gpu ? "NVIDIA GPU present" : "No NVIDIA GPU on this host"}
          </span>
        </div>

        <div className="divide-y">
          {rows.map(([key, s]) => (
            <div key={key} className="px-4 py-3 flex items-start gap-3">
              <span className={cn(
                "mt-0.5 p-1.5 rounded-lg shrink-0",
                s.configured ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-400"
              )}>
                {ICONS[key]}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-3">
                  <h4 className="text-xs font-bold text-slate-900">{s.service}</h4>
                  <ModeBadge mode={s.mode} />
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5 italic">{s.role}</p>
                <p className="text-xs text-slate-600 mt-1">{s.detail}</p>
                {s.model && (
                  <p className="text-[10px] font-mono text-slate-400 mt-1">{s.model}</p>
                )}
                {s.checks && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {s.checks.map((c) => (
                      <span key={c} className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                        {c}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Live guardrail demonstration */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div className="px-4 py-3 border-b flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-gray-800">Guardrailed explanation</h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Sample case: HR 142, SpO₂ 84. The verdict is decided first, then explained.
            </p>
          </div>
          <button
            onClick={runExplain}
            disabled={busy}
            className="tactile-button flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0b2545] text-white text-xs font-bold hover:bg-slate-800 transition disabled:opacity-50 shrink-0"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            RUN
          </button>
        </div>

        {result && (
          <div className="p-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2 py-0.5 rounded-md bg-red-100 text-red-700 text-[10px] font-bold">
                {result.triage_level}
              </span>
              <span className={cn(
                "px-2 py-0.5 rounded-md text-[10px] font-bold",
                result.source === "nemotron"
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-slate-100 text-slate-600"
              )}>
                source: {result.source}
              </span>
              <span className={cn(
                "px-2 py-0.5 rounded-md text-[10px] font-bold",
                result.guardrail_passed
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-amber-100 text-amber-700"
              )}>
                guardrail: {result.guardrail_passed ? "passed" : "blocked"}
              </span>
            </div>

            <p className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
              {result.explanation}
            </p>

            {result.guardrail_violations.length > 0 && (
              <div className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2.5">
                <strong>Blocked because:</strong> {result.guardrail_violations.join("; ")}.
                The nurse was shown deterministic rule text instead.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
