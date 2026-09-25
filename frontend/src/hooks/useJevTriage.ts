// src/hooks/useJevTriage.ts
// Feeds the patient's real stored vitals window into POST /api/v1/jev-triage.
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { JEVTriageResponse } from "../lib/types";

const FRAMES = 30;

export function useJevTriage(
  patientId: string | null | undefined,
  flags?: { fall?: boolean; sos?: boolean }
) {
  const fall = !!flags?.fall;
  const sos = !!flags?.sos;
  return useQuery<JEVTriageResponse>({
    queryKey: ["jev-triage", patientId, fall, sos],
    enabled: !!patientId,
    refetchInterval: 6000,
    staleTime: 4000,
    queryFn: async () => {
      const id = patientId as string;

      // GET /patient/{id}/history already returns ASCENDING chronological
      // order (it reverses its own DESC query before responding), which is
      // exactly what the scorer expects. Do not reverse again — doing so
      // feeds every trend in backwards, so a deteriorating patient reads as
      // recovering and the inverse-trend term never fires.
      const ordered = await api.patientHistory(id, FRAMES);

      return api.jevTriage({
        patient_id: id,
        heart_rate: ordered.map((r) => r.heart_rate ?? null),
        spo2: ordered.map((r) => r.spo2 ?? null),
        fall,
        sos,
      });
    },
  });
}
