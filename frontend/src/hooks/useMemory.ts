"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/services/api";
import type { MemoryDoc, MemoryListResponse, StatsOverview } from "@/types";

export interface ListParams {
  skip?: number;
  limit?: number;
  track?: string;
  memory_type?: string;
  status?: string;
  project_id?: string;
  has_open_loop?: boolean;
}

export function useMemory() {
  const [data, setData] = useState<MemoryListResponse | null>(null);
  const [doc, setDoc] = useState<MemoryDoc | null>(null);
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const listDocuments = useCallback(async (params: ListParams = {}) => {
    setIsLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
      });
      const data = await api.get<MemoryListResponse>(`memory?${qs.toString()}`);
      setData(data);
      return data;
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load memories");
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getDocument = useCallback(async (path: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get<MemoryDoc>(`memory/${path}`);
      setDoc(data);
      return data;
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load memory");
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateDocument = useCallback(
    async (path: string, body: Partial<MemoryDoc> & { content?: string }) => {
      try {
        const data = await api.put<MemoryDoc>(`memory/${path}`, body);
        setDoc(data);
        return data;
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Update failed");
        return null;
      }
    },
    [],
  );

  const createDocument = useCallback(
    async (body: { rel_path: string; content: string; memory_type?: string; track?: string; summary?: string; keywords?: string[] }) => {
      try {
        return await api.post<MemoryDoc>("memory", body);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Create failed");
        return null;
      }
    },
    [],
  );

  const deleteDocument = useCallback(async (path: string) => {
    try {
      await api.del(`memory/${path}`);
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Delete failed");
      return false;
    }
  }, []);

  const getStats = useCallback(async () => {
    try {
      const s = await api.get<StatsOverview>("memory/stats");
      setStats(s);
      return s;
    } catch {
      return null;
    }
  }, []);

  const rescan = useCallback(async () => {
    try {
      return await api.post<{ docs_indexed: number; duration_seconds: number }>("memory/rescan");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Rescan failed");
      return null;
    }
  }, []);

  return {
    data,
    doc,
    stats,
    isLoading,
    error,
    listDocuments,
    getDocument,
    updateDocument,
    createDocument,
    deleteDocument,
    getStats,
    rescan,
  };
}
