"use client";

import { useCallback, useState } from "react";
import { api, ApiError } from "@/services/api";
import type {
  MandolStatsResponse,
  MandolUnitInfo,
  MandolUnitListResponse,
  MandolUnitCreateRequest,
  SpaceInfo,
  SpaceListResponse,
  RelationshipInfo,
  RelationshipListResponse,
  SubgraphResponse,
  TraceResponse,
  MandolRetrieveResponse,
  MandolSearchHit,
  MandolAskResponse,
  BuildReportResponse,
  SnapshotResponse,
  ExternalStoreStatus,
  Neo4jSubgraph,
} from "@/types";

export function useMandol() {
  const [stats, setStats] = useState<MandolStatsResponse | null>(null);
  const [units, setUnits] = useState<MandolUnitInfo[]>([]);
  const [spaces, setSpaces] = useState<SpaceInfo[]>([]);
  const [retrieveResults, setRetrieveResults] = useState<MandolSearchHit[]>([]);
  const [askResult, setAskResult] = useState<MandolAskResponse | null>(null);
  const [buildReport, setBuildReport] = useState<BuildReportResponse | null>(null);
  const [subgraph, setSubgraph] = useState<SubgraphResponse | null>(null);
  const [traceResult, setTraceResult] = useState<TraceResponse | null>(null);
  const [relationships, setRelationships] = useState<RelationshipInfo[]>([]);
  const [externalStatus, setExternalStatus] = useState<ExternalStoreStatus | null>(null);
  const [neo4jSubgraph, setNeo4jSubgraph] = useState<Neo4jSubgraph | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleErr = (err: unknown, fallback: string) => {
    const msg = err instanceof ApiError ? err.detail : fallback;
    setError(msg);
    return null;
  };

  // ============ 统计与监控 ============
  const getStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get<MandolStatsResponse>("mandol/stats");
      setStats(data);
      return data;
    } catch (err) {
      return handleErr(err, "获取统计失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ============ 记忆单元 ============
  const listUnits = useCallback(async (limit = 100, offset = 0) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get<MandolUnitListResponse>(
        `mandol/units?limit=${limit}&offset=${offset}`
      );
      setUnits(data.items);
      return data;
    } catch (err) {
      return handleErr(err, "获取单元列表失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getUnit = useCallback(async (uid: string) => {
    setIsLoading(true);
    setError(null);
    try {
      return await api.get<MandolUnitInfo>(`mandol/units/${uid}`);
    } catch (err) {
      return handleErr(err, "获取单元失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createUnit = useCallback(async (req: MandolUnitCreateRequest) => {
    setIsLoading(true);
    setError(null);
    try {
      return await api.post<MandolUnitInfo>("mandol/units", req);
    } catch (err) {
      return handleErr(err, "创建单元失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const deleteUnit = useCallback(async (uid: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await api.del(`mandol/units/${uid}`);
      return true;
    } catch (err) {
      handleErr(err, "删除单元失败");
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ============ 空间管理 ============
  const listSpaces = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get<SpaceListResponse>("mandol/spaces");
      setSpaces(data.items);
      return data;
    } catch (err) {
      return handleErr(err, "获取空间列表失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createSpace = useCallback(async (name: string) => {
    setIsLoading(true);
    setError(null);
    try {
      return await api.post<SpaceInfo>("mandol/spaces", { name });
    } catch (err) {
      return handleErr(err, "创建空间失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const deleteSpace = useCallback(async (name: string, cascade = false) => {
    setIsLoading(true);
    setError(null);
    try {
      await api.del(`mandol/spaces/${name}?cascade=${cascade}`);
      return true;
    } catch (err) {
      handleErr(err, "删除空间失败");
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ============ 关系管理 ============
  const listRelationships = useCallback(async (uid: string, direction = "all") => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get<RelationshipListResponse>(
        `mandol/relationships?uid=${encodeURIComponent(uid)}&direction=${direction}`
      );
      setRelationships(data.relationships);
      return data;
    } catch (err) {
      return handleErr(err, "获取关系列表失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createRelationship = useCallback(
    async (source: string, target: string, rel_type: string, properties = {}) => {
      setIsLoading(true);
      setError(null);
      try {
        await api.post("mandol/relationships", { source, target, rel_type, properties });
        return true;
      } catch (err) {
        handleErr(err, "创建关系失败");
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // ============ 图谱遍历 ============
  const getEntitySubgraph = useCallback(
    async (query: string, maxDepth = 2, topK = 10) => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.post<SubgraphResponse>("mandol/graph/entity-subgraph", {
          query,
          max_depth: maxDepth,
          top_k: topK,
        });
        setSubgraph(data);
        return data;
      } catch (err) {
        return handleErr(err, "获取子图失败");
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const traceEvidence = useCallback(async (uid: string, maxDepth = 2, topK = 10) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.post<TraceResponse>("mandol/graph/trace-evidence", {
        uid,
        max_depth: maxDepth,
        top_k: topK,
      });
      setTraceResult(data);
      return data;
    } catch (err) {
      return handleErr(err, "溯源失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const traceCoref = useCallback(async (uid: string, maxDepth = 2, topK = 10) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.post<TraceResponse>("mandol/graph/trace-coref", {
        uid,
        max_depth: maxDepth,
        top_k: topK,
      });
      setTraceResult(data);
      return data;
    } catch (err) {
      return handleErr(err, "共指追踪失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ============ 检索 ============
  const retrieve = useCallback(
    async (
      query: string,
      options: {
        topK?: number;
        useRerank?: boolean;
        view?: string;
        spaceName?: string;
        skipViews?: string[];
      } = {}
    ) => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.post<MandolRetrieveResponse>("mandol/retrieve", {
          query,
          top_k: options.topK ?? 10,
          use_rerank: options.useRerank ?? true,
          view: options.view,
          space_name: options.spaceName,
          skip_views: options.skipViews,
        });
        setRetrieveResults(data.results);
        return data;
      } catch (err) {
        return handleErr(err, "检索失败");
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // ============ 智能问答 ============
  const ask = useCallback(
    async (
      query: string,
      options: {
        topK?: number;
        useRerank?: boolean;
        systemPrompt?: string;
        temperature?: number;
        maxTokens?: number;
      } = {}
    ) => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.post<MandolAskResponse>("mandol/ask", {
          query,
          top_k: options.topK ?? 5,
          use_rerank: options.useRerank ?? true,
          system_prompt: options.systemPrompt,
          temperature: options.temperature ?? 0.3,
          max_tokens: options.maxTokens,
        });
        setAskResult(data);
        return data;
      } catch (err) {
        return handleErr(err, "问答失败");
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // ============ 构建 ============
  const buildHighLevel = useCallback(async (mode = "auto") => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.post<BuildReportResponse>("mandol/build", { mode });
      setBuildReport(data);
      return data;
    } catch (err) {
      return handleErr(err, "构建失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ============ 持久化 ============
  const saveSnapshot = useCallback(async (storagePath?: string, wait = false) => {
    setIsLoading(true);
    setError(null);
    try {
      return await api.post<SnapshotResponse>("mandol/save", { storage_path: storagePath, wait });
    } catch (err) {
      return handleErr(err, "保存失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getSaveStatus = useCallback(async () => {
    try {
      return await api.get<{ in_progress: boolean; last_result: SnapshotResponse | null }>("mandol/save-status");
    } catch (err) {
      handleErr(err, "查询保存状态失败");
      return null;
    }
  }, []);

  const getExternalStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get<ExternalStoreStatus>("mandol/external-store-status");
      setExternalStatus(data);
      return data;
    } catch (err) {
      return handleErr(err, "查询外部存储状态失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getNeo4jSubgraph = useCallback(async (centerUid?: string, limit = 200) => {
    setIsLoading(true);
    setError(null);
    try {
      const url = centerUid
        ? `mandol/neo4j/subgraph?center_uid=${encodeURIComponent(centerUid)}&limit=${limit}`
        : `mandol/neo4j/subgraph?limit=${limit}`;
      const data = await api.get<Neo4jSubgraph>(url);
      setNeo4jSubgraph(data);
      return data;
    } catch (err) {
      return handleErr(err, "查询 Neo4j 子图失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const flush = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await api.post("mandol/flush");
      return true;
    } catch (err) {
      handleErr(err, "刷新失败");
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reconfigure = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await api.post("mandol/reconfigure");
      return true;
    } catch (err) {
      handleErr(err, "重新配置失败");
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    stats,
    units,
    spaces,
    retrieveResults,
    askResult,
    buildReport,
    subgraph,
    traceResult,
    relationships,
    externalStatus,
    neo4jSubgraph,
    isLoading,
    error,
    // 统计
    getStats,
    // 单元
    listUnits,
    getUnit,
    createUnit,
    deleteUnit,
    // 空间
    listSpaces,
    createSpace,
    deleteSpace,
    // 关系
    listRelationships,
    createRelationship,
    // 图谱
    getEntitySubgraph,
    traceEvidence,
    traceCoref,
    getNeo4jSubgraph,
    // 检索
    retrieve,
    // 问答
    ask,
    // 构建
    buildHighLevel,
    // 持久化
    saveSnapshot,
    getSaveStatus,
    getExternalStatus,
    flush,
    reconfigure,
  };
}
