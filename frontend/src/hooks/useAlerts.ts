// src/hooks/useAlerts.ts – fetch recent alerts and alert history
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { AlertEvent } from "../lib/types";

export function useAlerts() {
  return useQuery<AlertEvent[]>({
    queryKey: ["alerts"],
    queryFn: api.alerts,
    staleTime: 1000 * 30,
    refetchInterval: 5000,
  });
}

export function useAlertHistory() {
  return useQuery<AlertEvent[]>({
    queryKey: ["history"],
    queryFn: api.history,
    staleTime: 1000 * 60,
    refetchInterval: 15000,
  });
}
