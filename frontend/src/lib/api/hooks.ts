"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type AlertsOut, type MeetingsOut, type StatusOut } from "./client";

export function useMeetings() {
  return useQuery<MeetingsOut>({
    queryKey: ["meetings"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/meetings");
      if (error || !data) throw new Error("Failed to load meetings");
      return data;
    },
  });
}

export function useAlerts() {
  return useQuery<AlertsOut>({
    queryKey: ["alerts"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/alerts", { params: { query: { limit: 30 } } });
      if (error || !data) throw new Error("Failed to load alerts");
      return data;
    },
  });
}

export function useStatus() {
  return useQuery<StatusOut>({
    queryKey: ["status"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/status");
      if (error || !data) throw new Error("Failed to load status");
      return data;
    },
  });
}
