"use client";

import { useCallback, useState } from "react";
import { api, ApiError } from "@/services/api";
import type {
  ConvertResponse,
  ParseResponse,
  SaveResponse,
  UploadResponse,
} from "@/types";

export type ImportStep = "upload" | "parse" | "convert" | "save";

export function useDocumentImport() {
  const [step, setStep] = useState<ImportStep>("upload");
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [parsed, setParsed] = useState<ParseResponse | null>(null);
  const [converted, setConverted] = useState<ConvertResponse | null>(null);
  const [saved, setSaved] = useState<SaveResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

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
    } catch (err) {
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

  const save = useCallback(async (fileId: string, memoryFiles: ConvertResponse["memory_files"], buildMandol = true) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.post<SaveResponse>(`documents/${fileId}/save`, {
        memory_files: memoryFiles,
        build_mandol: buildMandol,
      });
      setSaved(data);
      setProgress(100);
      setStep("save");
      return data;
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "保存失败");
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setStep("upload");
    setUpload(null);
    setParsed(null);
    setConverted(null);
    setSaved(null);
    setProgress(0);
    setError(null);
  }, []);

  return {
    step,
    progress,
    upload,
    parsed,
    converted,
    saved,
    isLoading,
    error,
    uploadFile,
    parse,
    convert,
    save,
    reset,
  };
}
