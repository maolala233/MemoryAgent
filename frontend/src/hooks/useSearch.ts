"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/services/api";
import type { SearchRequest, SearchResponse, SearchFilters } from "@/types";

export function useSearch() {
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem("codex:search-history");
    if (raw) setHistory(JSON.parse(raw).slice(0, 10));
  }, []);

  const search = useCallback(async (req: SearchRequest) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.post<SearchResponse>("search", req as unknown as Record<string, unknown>);
      setResults(data);
      if (typeof window !== "undefined") {
        const next = [req.query, ...history.filter((q) => q !== req.query)].slice(0, 10);
        setHistory(next);
        window.localStorage.setItem("codex:search-history", JSON.stringify(next));
      }
      return data;
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Search failed";
      setError(msg);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [history]);

  const getSuggestions = useCallback(async (q: string) => {
    if (!q.trim()) return [];
    try {
      return await api.get<string[]>(`search/suggestions?q=${encodeURIComponent(q)}`);
    } catch {
      return [];
    }
  }, []);

  const getFilters = useCallback(async () => {
    try {
      return await api.get<SearchFilters>("search/filters");
    } catch {
      return { tracks: [], memory_types: [], projects: [] } as SearchFilters;
    }
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("codex:search-history");
    }
  }, []);

  return { results, isLoading, error, history, search, getSuggestions, getFilters, clearHistory };
}
