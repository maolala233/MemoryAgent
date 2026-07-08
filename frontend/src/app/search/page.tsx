"use client";

import { Suspense, useEffect, useState, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { useSearch } from "@/hooks/useSearch";
import type { MemoryResult, SearchFilters } from "@/types";

type Strategy = "keyword" | "semantic" | "hybrid" | "mandol" | "entity" | "event" | "graph" | "causal";

const STRATEGY_LABELS: Record<Strategy, string> = {
  keyword: "关键词",
  semantic: "语义",
  hybrid: "混合",
  mandol: "Mandol 全息",
  entity: "实体",
  event: "事件",
  graph: "图谱",
  causal: "因果",
};

function highlight(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length > 1);
  if (terms.length === 0) return text;
  const pattern = new RegExp(
    `(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`,
    "gi",
  );
  const parts = text.split(pattern);
  return parts.map((part, i) =>
    pattern.test(part) ? (
      <mark
        key={i}
        className="bg-primary-fixed text-primary font-bold px-0.5 rounded"
      >
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

function ResultCard({ result, query, isMandol }: { result: MemoryResult; query: string; isMandol: boolean }) {
  if (isMandol) {
    const scorePct = Math.round((result.score || 0) * 100);
    return (
      <div className="result-card bg-surface border border-border p-5 rounded-xl hover:border-primary transition-all cursor-pointer group">
        <div className="flex justify-between items-start mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <Icon name="memory" className="text-primary text-[20px] flex-shrink-0" />
            <h3 className="text-body-lg font-bold text-on-surface truncate">
              {result.uid || "未知单元"}
            </h3>
          </div>
          {result.score !== undefined && (
            <Pill variant={scorePct >= 80 ? "success" : scorePct >= 50 ? "info" : "default"} size="sm">
              {result.score.toFixed(4)}
            </Pill>
          )}
        </div>
        <p className="text-body-md text-on-surface-variant mb-3 leading-relaxed line-clamp-3">
          {result.text ? highlight(result.text, query) : "无预览"}
        </p>
        {/* 分数详情 */}
        {result.scores && Object.keys(result.scores).length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mb-2">
            {Object.entries(result.scores).map(([key, val]) => (
              <span key={key} className="text-label-sm text-on-surface-variant bg-surface-container-low px-2 py-0.5 rounded">
                {key}: {typeof val === "number" ? val.toFixed(4) : val}
              </span>
            ))}
          </div>
        )}
        {/* 空间标签 */}
        {result.metadata?.spaces && (
          <div className="flex flex-wrap items-center gap-2">
            {(result.metadata.spaces as string[]).map((space) => (
              <Pill key={space} variant="info" size="sm">{space}</Pill>
            ))}
          </div>
        )}
      </div>
    );
  }

  const scorePct = Math.round((result.score || 0) * 100);
  const scoreVariant = scorePct >= 80 ? "success" : scorePct >= 50 ? "info" : "default";

  return (
    <div className="result-card bg-surface border border-border p-5 rounded-xl hover:border-primary transition-all cursor-pointer group">
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <Icon name="description" className="text-primary text-[20px] flex-shrink-0" />
          <h3 className="text-body-lg font-bold text-on-surface title-link transition-colors truncate">
            {result.title || result.rel_path}
          </h3>
        </div>
        <Pill variant={scoreVariant} size="sm">
          <span className={`w-1.5 h-1.5 rounded-full ${
            scoreVariant === "success" ? "bg-success" : scoreVariant === "info" ? "bg-primary" : "bg-outline"
          }`} />
          {scorePct}%
        </Pill>
      </div>
      <p className="text-body-md text-on-surface-variant mb-4 leading-relaxed line-clamp-3">
        {result.snippet ? highlight(result.snippet, query) : "无预览"}
      </p>
      <div className="flex flex-wrap items-center gap-3">
        {result.track && <Pill variant="info" size="sm">{result.track}</Pill>}
        {result.memory_type && <Pill size="sm">{result.memory_type}</Pill>}
        <span className="ml-auto text-label-sm text-outline font-mono truncate">
          {result.rel_path}
        </span>
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<Loading size="lg" label="加载搜索中..." />}>
      <SearchContent />
    </Suspense>
  );
}

function SearchContent() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") || "";
  const { results, isLoading, error, history, search, getFilters, clearHistory } = useSearch();
  const [query, setQuery] = useState(initialQuery);
  const [strategy, setStrategy] = useState<Strategy>("mandol");
  const [filters, setFilters] = useState<SearchFilters | null>(null);
  const [track, setTrack] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const isMandolStrategy = ["mandol", "entity", "event", "graph", "causal"].includes(strategy);

  useEffect(() => {
    getFilters().then(setFilters);
  }, [getFilters]);

  useEffect(() => {
    if (initialQuery) {
      setQuery(initialQuery);
      doSearch(initialQuery, strategy);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  const doSearch = (q: string, s: Strategy) => {
    if (!q.trim()) return;
    search({
      query: q,
      strategy: s,
      track: track || undefined,
      limit: 20,
    });
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doSearch(query, strategy);
  };

  const onStrategyChange = (s: Strategy) => {
    setStrategy(s);
    if (query.trim()) doSearch(query, s);
  };

  return (
    <AppShell noTopBar>
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* 搜索头部 */}
        <div className="px-panel-padding py-8 bg-surface-bright border-b border-border">
          <div className="w-full space-y-4">
            <form onSubmit={onSubmit} className="relative">
              <Icon
                name="search"
                className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant text-[24px]"
              />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="输入搜索内容..."
                className="w-full pl-12 pr-4 py-4 bg-surface border border-border rounded-xl focus:ring-2 focus:ring-primary focus:border-primary outline-none text-body-lg shadow-sm transition-all"
                autoFocus
              />
              <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
                {query && (
                  <button
                    type="button"
                    onClick={() => {
                      setQuery("");
                      inputRef.current?.focus();
                    }}
                    className="p-1 text-on-surface-variant hover:text-on-surface rounded"
                  >
                    <Icon name="close" className="text-[18px]" />
                  </button>
                )}
                <kbd className="text-label-sm text-on-surface-variant bg-surface-container px-2 py-1 rounded border border-border">
                  ⌘K
                </kbd>
              </div>
            </form>

            <div className="flex items-center justify-center gap-4">
              <div className="inline-flex p-1 bg-surface-container rounded-lg border border-border flex-wrap">
                {(Object.keys(STRATEGY_LABELS) as Strategy[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => onStrategyChange(s)}
                    className={[
                      "px-4 py-1.5 rounded-md text-label-md transition-all",
                      strategy === s
                        ? "bg-surface shadow-sm text-primary font-bold"
                        : "text-on-surface-variant hover:text-on-surface",
                    ].join(" ")}
                  >
                    {STRATEGY_LABELS[s]}
                  </button>
                ))}
              </div>
              {!isMandolStrategy && filters && filters.tracks.length > 0 && (
                <>
                  <div className="h-4 w-px bg-border" />
                  <select
                    value={track}
                    onChange={(e) => {
                      setTrack(e.target.value);
                      if (query.trim()) {
                        search({ query, strategy, track: e.target.value || undefined, limit: 20 });
                      }
                    }}
                    className="px-3 py-1.5 bg-surface border border-border rounded-lg text-label-md focus:ring-2 focus:ring-primary outline-none"
                  >
                    <option value="">全部分类</option>
                    {filters.tracks.map((tr) => (
                      <option key={tr} value={tr}>{tr}</option>
                    ))}
                  </select>
                </>
              )}
              {results && (
                <>
                  <div className="h-4 w-px bg-border" />
                  <div className="flex items-center gap-2">
                    <span className="text-label-sm text-on-surface-variant">结果:</span>
                    <span className="text-label-md font-bold text-on-surface">
                      {results.total} 条
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* 结果列表 */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-panel-padding py-6">
          <div className="w-full space-y-4">
            {error && (
              <div className="bg-error/10 border border-error/20 text-error rounded-lg p-4 flex items-center gap-2">
                <Icon name="error" filled />
                <span className="text-body-md">{error}</span>
              </div>
            )}

            {isLoading && <Loading label="搜索中..." />}

            {!isLoading && !results && !query && (
              <div className="space-y-6">
                {history.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-body-md font-bold text-on-surface-variant">最近搜索</h3>
                      <button onClick={clearHistory} className="text-label-sm text-on-surface-variant hover:text-error">
                        清除
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {history.map((q) => (
                        <button
                          key={q}
                          onClick={() => { setQuery(q); doSearch(q, strategy); }}
                          className="px-3 py-1.5 bg-surface-container rounded-full text-label-md text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-all"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <EmptyState
                  icon="search"
                  title="记忆搜索"
                  description="输入关键词或问题，从记忆库中检索相关信息。支持关键词、语义、混合、Mandol全息、图谱等多种检索策略。"
                />
              </div>
            )}

            {!isLoading && results && results.results.length === 0 && (
              <EmptyState
                icon="search_off"
                title="未找到结果"
                description={`没有找到与 "${query}" 相关的记忆。试试其他关键词或切换检索策略。`}
              />
            )}

            {!isLoading && results && results.results.length > 0 && (
              <div className="space-y-4">
                {results.results.map((result, i) => (
                  <ResultCard
                    key={result.uid || result.rel_path || i}
                    result={result}
                    query={query}
                    isMandol={isMandolStrategy}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
