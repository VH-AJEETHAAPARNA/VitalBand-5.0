// src/hooks/useAlertDetail.ts – fetch a single alert by ID (via history endpoint filter)
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { AlertEvent } from "../lib/types";

export function useAlertDetail(id: number) {
  return useQuery<AlertEvent>({
    queryKey: ["alert", id],
    queryFn: async () => {
      const history = await api.history();
      const found = history.find((a) => a.id === id);
      if (!found) throw new Error("Alert not found");
      return found;
    },
    staleTime: 1000 * 60,
  });
}
