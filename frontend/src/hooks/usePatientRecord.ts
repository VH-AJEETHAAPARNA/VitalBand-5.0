// src/hooks/usePatientRecord.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { PatientRecord } from "../lib/types";

export function usePatientRecord(patientId: string | null | undefined) {
  return useQuery<PatientRecord>({
    queryKey: ["patient-record", patientId],
    enabled: !!patientId,
    // Admissions data barely changes; no need to poll it like vitals.
    staleTime: 60_000,
    queryFn: () => api.patientRecord(patientId as string),
  });
}
