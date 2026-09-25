// src/hooks/usePatients.ts – React Query hooks for patient data
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Patient } from "../lib/types";

export function usePatients(options?: { enabled?: boolean }) {
  return useQuery<Patient[]>({
    queryKey: ["patients"],
    queryFn: api.patients,
    staleTime: 1000 * 30, // 30s
    refetchInterval: 5000, // poll every 5s for live updates
    enabled: options?.enabled ?? true,
  });
}

export function usePatient(patientId: string) {
  return useQuery<Patient>({
    queryKey: ["patient", patientId],
    queryFn: () => api.patient(patientId),
    staleTime: 1000 * 30,
  });
}
