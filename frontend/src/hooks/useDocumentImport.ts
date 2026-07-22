"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/services/api";
import type {
  ConvertResponse,
  ParseResponse,
  SaveResponse,
  UploadResponse,
} from "@/types";

export type ImportStep = "upload" | "parse" | "convert" | "save";

export interface BuildExtraction {
  entity_count: number;
  event_count: number;
  entities_added: number;
  events_added: number;
  entities_extracted: number;
  events_extracted: number;
  entities_deduped: number;
  events_deduped: number;
  total_units: number;
}

export interface BuildStatus {
  status: "idle" | "running" | "completed" | "failed" | "busy";
  message: string;
  started_at: number;
  finished_at: number;
  elapsed_seconds: number;
  result: null | {
    status?: string;
    message?: string;
    units_processed?: number;
    sessions_processed?: number;
    duration_seconds?: number;
    extraction?: BuildExtraction;
    neo4j_sync?: { nodes?: number; edges?: number; status?: string };
  };
}

export function useDocumentImport() {
  const [step, setStep] = useState<ImportStep>("upload");
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [parsed, setParsed] = useState<ParseResponse | null>(null);
  const [converted, setConverted] = useState<ConvertResponse | null>(null);
  const [saved, setSaved] = useState<SaveResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [buildStatus, setBuildStatus] = useState<BuildStatus | null>(null);
  const buildTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopBuildPolling = useCallback(() => {
    if (buildTimerRef.current) {
      clearTimeout(buildTimerRef.current);
      buildTimerRef.current = null;
    }
  }, []);

  const pollBuildStatus = useCallback(() => {
    stopBuildPolling();
    const tick = async () => {
      try {
        const s = await api.get<BuildStatus>("mandol/build-status");
        setBuildStatus(s);
        if (s.status === "running") {
          buildTimerRef.current = setTimeout(tick, 1500);
        } else {
          // completed / failed / idle -> 停轮询
          buildTimerRef.current = null;
        }
      } catch {
        // 网络抖动：重试
        buildTimerRef.current = setTimeout(tick, 3000);
      }
    };
    tick();
  }, [stopBuildPolling]);

  useEffect(() => {
    return () => stopBuildPolling();
  }, [stopBuildPolling]);

  const uploadFile = useCallback(async (file: File) => {
    setIsLoading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const data = await api.post<UploadResponse>("documents/upload", fd);
      setUpload(data);
      setProgress(25);
      setStep("parse");
      return data;
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Upload failed");
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const parse = useCallback(async (fileId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.post<ParseResponse>(`documents/${fileId}/parse`);
      setParsed(data);
      setProgress(50);
      setStep("convert");
      return data;
    } catch (err)      {
      setError(err instanceof ApiError ? err.detail : "Parse failed");
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const convert = useCallback(
    async (fileId: string, opts: { project_id?: string; memory_type?: string; strategy?: string }) => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.post<ConvertResponse>(
          `documents/${fileId}/convert-to-memory`,
          opts,
        );
        setConverted(data);
        setProgress(75);
        setStep("save");
        return data;
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Convert failed");
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const save = useCallback(
    async (
      fileId: string,
      memoryFiles: ConvertResponse["memory_files"],
      buildMandol = true,
      projectId?: string,
    ) => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.post<SaveResponse>(`documents/${fileId}/save`, {
          memory_files: memoryFiles,
          build_mandol: buildMandol,
          project_id: projectId || undefined,
        });
        setSaved(data);
        setProgress(100);
        // 保持在 "save" 步骤; build 进度通过日志面板展示
        setStep("save");
        if (buildMandol) {
          setBuildStatus({
            status: "running",
            message: "正在排队构建...",
            started_at: 0,
            finished_at: 0,
            elapsed_seconds: 0,
            result: null,
          });
          pollBuildStatus();
        }
        return data;
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "保存失败");
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [pollBuildStatus],
  );

  const reset = useCallback(() => {
    stopBuildPolling();
    setStep("upload");
    setUpload(null);
    setParsed(null);
    setConverted(null);
    setSaved(null);
    setProgress(0);
    setError(null);
    setBuildStatus(null);
  }, [stopBuildPolling]);

  return {
    step,
    progress,
    upload,
    parsed,
    converted,
    saved,
    isLoading,
    error,
    buildStatus,
    uploadFile,
    parse,
    convert,
    save,
    reset,
    stopBuildPolling,
  };
}
