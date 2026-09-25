// src/hooks/useVitalsHistory.ts – fetch time-series vitals history for charting
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { VitalsReading } from "../lib/types";

export function useVitalsHistory(patientId: string, limit = 60) {
  return useQuery<VitalsReading[]>({
    queryKey: ["vitalsHistory", patientId, limit],
    queryFn: () => api.patientHistory(patientId, limit),
    enabled: !!patientId,
    refetchInterval: 3000, // refresh chart data every 3s
  });
}
