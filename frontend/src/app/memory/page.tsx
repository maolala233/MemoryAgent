"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pagination } from "@/components/shared/Pagination";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMemory } from "@/hooks/useMemory";
import { api } from "@/services/api";
import type { MemoryDoc } from "@/types";

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

// 状态/类型的友好显示名（数据库里仍是英文，仅在 UI 翻译）
const STATUS_LABELS: Record<string, string> = {
  active: "活跃",
  verified: "已验证",
  archived: "已归档",
  draft: "草稿",
};
const TYPE_LABELS: Record<string, string> = {
  note: "笔记",
  imported_document: "导入文档",
  meeting: "会议",
  decision: "决策",
  project: "项目",
  workflow: "工作流",
  reference: "参考",
};
const TRACK_LABELS: Record<string, string> = {
  note: "笔记",
  decision: "决策",
  project: "项目",
  workflow: "工作流",
};
const translateValue = (map: Record<string, string>, raw: string): string => map[raw] ?? raw;

export default function MemoryVaultPage() {
  return (
    <Suspense fallback={<Loading size="lg" label="Loading vault..." />}>
      <MemoryVaultContent />
    </Suspense>
  );
}

function MemoryVaultContent() {
  const searchParams = useSearchParams();
  const { data, isLoading, listDocuments } = useMemory();
  const [track, setTrack] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [hasOpenLoop, setHasOpenLoop] = useState(false);
  const [search, setSearch] = useState("");
  // 分页状态
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // 一次性从后端拉取所有可选的 track / type 候选，避免被过滤后的 items 截断
  const [trackOptions, setTrackOptions] = useState<string[]>([]);
  const [typeOptions, setTypeOptions] = useState<string[]>([]);

  useEffect(() => {
    api
      .get<{ tracks: string[]; memory_types: string[]; projects: string[] }>("search/filters")
      .then((d) => {
        setTrackOptions((d.tracks || []).filter(Boolean));
        setTypeOptions((d.memory_types || []).filter(Boolean));
      })
      .catch(() => {
        // 失败时回退到当前 items 中提取（行为同旧版）
      });
  }, []);

  useEffect(() => {
    const filter = searchParams.get("filter");
    if (filter === "open-loops") setHasOpenLoop(true);
  }, [searchParams]);

  useEffect(() => {
    listDocuments({
      track: track || undefined,
      memory_type: type || undefined,
      status: status || undefined,
      has_open_loop: hasOpenLoop || undefined,
      skip: (page - 1) * pageSize,
      limit: pageSize,
    });
  }, [track, type, status, hasOpenLoop, page, pageSize, listDocuments]);

  // 切换筛选时回到第一页, 避免越界
  useEffect(() => {
    setPage(1);
  }, [track, type, status, hasOpenLoop]);

  // 越界保护: total 变化后若当前页超出范围, 自动回退
  const total = data?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  useEffect(() => {
    if (page > lastPage) setPage(lastPage);
  }, [page, lastPage]);

  const filtered = useMemo(() => {
    if (!data?.items) return [];
    if (!search.trim()) return data.items;
    const q = search.toLowerCase();
    return data.items.filter(
      (m) =>
        (m.title || "").toLowerCase().includes(q) ||
        m.rel_path.toLowerCase().includes(q) ||
        (m.summary || "").toLowerCase().includes(q) ||
        m.keywords.some((k) => k.toLowerCase().includes(q)),
    );
  }, [data, search]);

  // 优先用后端返回的全量候选；若失败再回退到当前 items
  const tracks = useMemo(
    () =>
      trackOptions.length > 0
        ? trackOptions
        : Array.from(new Set(data?.items.map((m) => m.track).filter(Boolean))) as string[],
    [trackOptions, data],
  );
  const types = useMemo(
    () =>
      typeOptions.length > 0
        ? typeOptions
        : Array.from(new Set(data?.items.map((m) => m.memory_type).filter(Boolean))) as string[],
    [typeOptions, data],
  );

  const clearFilters = () => {
    setTrack("");
    setType("");
    setStatus("");
    setHasOpenLoop(false);
    setSearch("");
  };

  return (
    <AppShell title="记忆库" subtitle={`${data?.total ?? 0} 条`}>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[240px]">
              <Icon
                name="search"
                className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant"
              />
              <input
                type="text"
                placeholder="搜索记忆（标题 / 关键词 / 路径）"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none text-body-md"
              />
            </div>
            <select
              value={track}
              onChange={(e) => setTrack(e.target.value)}
              className="px-3 py-2 bg-surface border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
            >
              <option value="">全部轨道</option>
              {tracks.map((t) => (
                <option key={t} value={t}>
                  {translateValue(TRACK_LABELS, t)}
                </option>
              ))}
            </select>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="px-3 py-2 bg-surface border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
            >
              <option value="">全部类型</option>
              {types.map((t) => (
                <option key={t} value={t}>
                  {translateValue(TYPE_LABELS, t)}
                </option>
              ))}
            </select>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="px-3 py-2 bg-surface border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
            >
              <option value="">任意状态</option>
              <option value="active">活跃</option>
              <option value="verified">已验证</option>
              <option value="archived">已归档</option>
              <option value="draft">草稿</option>
            </select>
            <label className="flex items-center gap-2 text-body-md text-on-surface-variant cursor-pointer">
              <input
                type="checkbox"
                checked={hasOpenLoop}
                onChange={(e) => setHasOpenLoop(e.target.checked)}
                className="rounded border-border"
              />
              仅显示未闭环
            </label>
            {(track || type || status || hasOpenLoop || search) && (
              <button
                onClick={clearFilters}
                className="text-label-md text-on-surface-variant hover:text-error transition-colors flex items-center gap-1"
              >
                <Icon name="close" className="text-[14px]" />
                清除筛选
              </button>
            )}
            <Link
              href="/memory/new"
              className="ml-auto flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-md hover:opacity-90 transition-opacity"
            >
              <Icon name="add" className="text-[18px]" />
              新建记忆
            </Link>
          </div>

          {/* List */}
          {isLoading && !data && <Loading label="正在加载记忆…" />}

          {data && filtered.length === 0 && (
            <EmptyState
              icon="inventory_2"
              title="未找到匹配的记忆"
              description="尝试调整筛选条件，或新建一条记忆。"
              action={
                <Link
                  href="/memory/new"
                  className="px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-md"
                >
                  + 新建记忆
                </Link>
              }
            />
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filtered.map((m: MemoryDoc) => {
              // 数据里偶有重复 keyword，去重以避免 React key 重复警告
              const uniqueKeywords = Array.from(new Set(m.keywords || [])).slice(0, 3);
              return (
              <Link
                key={m.rel_path}
                href={`/memory/${encodeURIComponent(m.rel_path)}`}
                className="block bg-surface border border-border rounded-xl p-4 hover:border-primary transition-colors group"
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Icon
                      name="description"
                      className="text-on-surface-variant group-hover:text-primary text-[20px] flex-shrink-0"
                    />
                    <h3 className="text-body-md font-bold text-on-surface truncate">
                      {m.title || m.rel_path}
                    </h3>
                  </div>
                  {m.open_loops.length > 0 && (
                    <Pill variant="warning" size="sm">
                      <Icon name="pending" className="text-[12px]" />
                      {m.open_loops.length}
                    </Pill>
                  )}
                </div>
                <p className="text-body-sm text-on-surface-variant mb-3 line-clamp-2">
                  {m.summary || m.content.slice(0, 140) + "..." || "无摘要。"}
                </p>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Pill variant="info" size="sm">
                    {translateValue(TRACK_LABELS, m.track)}
                  </Pill>
                  <Pill size="sm">{translateValue(TYPE_LABELS, m.memory_type)}</Pill>
                  <Pill variant={m.status === "verified" ? "success" : "default"} size="sm">
                    {translateValue(STATUS_LABELS, m.status)}
                  </Pill>
                  {uniqueKeywords.map((k) => (
                    <Pill key={k} variant="primary" size="sm">
                      #{k}
                    </Pill>
                  ))}
                  <span className="ml-auto text-label-sm text-outline">
                    {formatDate(m.updated_at || m.indexed_at)}
                  </span>
                </div>
                <p className="text-label-sm text-outline mt-2 font-mono truncate">
                  {m.rel_path}
                </p>
              </Link>
              );
            })}
          </div>
          {/* 分页 */}
          <div className="bg-surface-bright rounded-lg border border-border px-4 py-3">
            <Pagination
              page={page}
              pageSize={pageSize}
              total={total}
              onPageChange={setPage}
              onPageSizeChange={(n) => {
                setPageSize(n);
                setPage(1);
              }}
            />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
