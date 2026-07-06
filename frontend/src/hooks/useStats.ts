"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/services/api";
import type {
  OpenLoopItem,
  StatsDistribution,
  StatsOverview,
  TimelinePoint,
  MemoryListResponse,
} from "@/types";

export function useStats() {
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [distribution, setDistribution] = useState<StatsDistribution | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [openLoops, setOpenLoops] = useState<OpenLoopItem[]>([]);
  const [recent, setRecent] = useState<MemoryListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [o, d, t, loops, rec] = await Promise.all([
        api.get<StatsOverview>("stats/overview"),
        api.get<StatsDistribution>("stats/distribution"),
        api.get<TimelinePoint[]>("stats/timeline?days=30"),
        api.get<OpenLoopItem[]>("stats/open-loops"),
        api.get<MemoryListResponse>("memory?limit=5"),
      ]);
      setOverview(o);
      setDistribution(d);
      setTimeline(t);
      setOpenLoops(loops);
      setRecent(rec);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load stats");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { overview, distribution, timeline, openLoops, recent, isLoading, error, refresh };
}
