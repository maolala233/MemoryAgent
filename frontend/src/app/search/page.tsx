"use client";

import { Suspense, useEffect, useState, useRef, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { useSearch } from "@/hooks/useSearch";
import type { MemoryResult, SearchFilters } from "@/types";

type Strategy = "mandol" | "entity" | "event" | "graph" | "keyword";

const STRATEGY_LABELS: Record<Strategy, string> = {
  mandol: "全息检索",
  entity: "实体关系",
  event: "事件因果",
  graph: "图谱扩展",
  keyword: "关键词",
};

function highlight(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length > 1);
  if (terms.length === 0) return text;
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(${escaped.join("|")})`, "gi");
  const testRe = new RegExp(`^(?:${escaped.join("|")})$`, "i");
  const parts = text.split(pattern);
  return parts.map((part, i) =>
    typeof part === "string" && testRe.test(part) ? (
      <mark
        key={i}
        className="bg-yellow-200 text-amber-900 font-semibold px-0.5 rounded"
      >
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

function extractMatchedTerms(text: string, query: string): string[] {
  if (!query.trim() || !text) return [];
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length > 1);
  if (terms.length === 0) return [];
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(escaped.join("|"), "gi");
  const matches = text.match(re) || [];
  return Array.from(new Set(matches.map((m) => m.toLowerCase())));
}

function explainRelevance(result: MemoryResult, isMandol: boolean, query: string): string {
  if (isMandol) {
    const meta = (result.metadata || {}) as Record<string, unknown>;
    const typeLabel = (meta.type as string) || (result.uid?.startsWith("event:") ? "事件" : result.uid?.startsWith("entity:") ? "实体" : "记忆");
    const text = (result.text || result.snippet || "") as string;
    const matched = extractMatchedTerms(text, query);
    if (matched.length > 0) {
      return `命中 ${typeLabel} 中包含关键词：${matched.slice(0, 3).join("、")}`;
    }
    if (meta.entity_name || meta.event_name) {
      return `基于 Mandol 多视图语义匹配：${meta.entity_name || meta.event_name}`;
    }
    return "基于 Mandol 跨视图语义相似度计算";
  }
  const matched = extractMatchedTerms(result.snippet || "", query);
  if (matched.length > 0) {
    return `文本匹配命中关键词：${matched.slice(0, 3).join("、")}`;
  }
  return "基于向量语义相似度匹配";
}

function _formatUid(uid: string): { label: string; type: string } {
  if (!uid) return { label: "未知单元", type: "unit" };
  if (uid.startsWith("entity:")) return { label: uid.slice(7), type: "实体" };
  if (uid.startsWith("event:")) return { label: uid.slice(6), type: "事件" };
  if (uid.startsWith("summary:")) return { label: uid.slice(8), type: "摘要" };
  if (uid.startsWith("doc:")) {
    const parts = uid.split(":");
    const filePath = parts[1] || "";
    const fileName = filePath.split("/").pop() || filePath;
    const chunkIdx = parts.find((p) => p.startsWith("chunk:"));
    return { label: fileName, type: chunkIdx ? `文档片段 ${chunkIdx}` : "文档" };
  }
  return { label: uid, type: "单元" };
}

function ResultCard({ result, query, isMandol }: { result: MemoryResult; query: string; isMandol: boolean }) {
  const href = isMandol
    ? `/units?uid=${encodeURIComponent(result.uid || "")}`
    : `/memory/${(result.rel_path || "")
        .split("/")
        .filter(Boolean)
        .map((seg) => encodeURIComponent(seg))
        .join("/")}`;

  if (isMandol) {
    const rawScore = result.score || 0;
    // Mandol rerank 分数通常 0-10，归一化为百分比
    const scorePct = Math.min(100, Math.round((rawScore / 10) * 100));
    const { label, type } = _formatUid(result.uid || "");
    const meta = result.metadata || {};
    const matched = extractMatchedTerms(result.text || "", query);
    return (
      <Link href={href} className="block">
        <div className="result-card bg-surface border border-border p-5 rounded-xl hover:border-primary hover:shadow-md transition-all cursor-pointer group">
          <div className="flex justify-between items-start mb-2">
            <div className="flex items-center gap-2 min-w-0">
              <Icon name="memory" className="text-primary text-[20px] flex-shrink-0" />
              <span className="px-2 py-0.5 bg-primary-fixed text-primary rounded text-label-sm flex-shrink-0">
                {type}
              </span>
              <h3 className="text-body-lg font-bold text-on-surface truncate" title={result.uid || undefined}>
                {label}
              </h3>
            </div>
            {result.score !== undefined && (
              <Pill variant={scorePct >= 70 ? "success" : scorePct >= 40 ? "info" : "default"} size="sm">
                {scorePct}%
              </Pill>
            )}
          </div>
          <p className="text-body-md text-on-surface-variant mb-3 leading-relaxed line-clamp-3">
            {result.text ? highlight(result.text, query) : "无预览"}
          </p>
          {/* 相关性解释 */}
          <div className="flex items-center gap-1.5 mb-2 text-label-sm text-primary">
            <Icon name="auto_awesome" className="text-[14px]" />
            <span className="truncate">{explainRelevance(result, isMandol, query)}</span>
          </div>
          {/* 命中关键词标签 */}
          {matched.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mb-2">
              {matched.slice(0, 5).map((m) => (
                <span key={m} className="px-2 py-0.5 bg-yellow-100 text-amber-800 rounded text-label-sm border border-yellow-200">
                  命中: {m}
                </span>
              ))}
            </div>
          )}
          {/* 分数详情 */}
          {result.scores && Object.keys(result.scores).length > 0 && (
            <div className="flex flex-wrap items-center gap-2 mb-2">
              {Object.entries(result.scores as Record<string, number>).map(([key, val]) => (
                <span key={key} className="text-label-sm text-on-surface-variant bg-surface-container-low px-2 py-0.5 rounded">
                  {key}: {typeof val === "number" ? val.toFixed(4) : String(val)}
                </span>
              ))}
            </div>
          )}
          {/* 空间标签 + 来源 */}
          <div className="flex flex-wrap items-center gap-2">
            {meta.spaces && Array.isArray(meta.spaces)
              ? (meta.spaces as string[]).map((space: string) => (
                  <Pill key={space} variant="info" size="sm">{space}</Pill>
                ))
              : null}
            <span className="ml-auto text-label-sm text-outline font-mono truncate max-w-[50%]" title={result.uid || undefined}>
              {result.uid}
            </span>
          </div>
        </div>
      </Link>
    );
  }

  const scorePct = Math.round((result.score || 0) * 100);
  const scoreVariant = scorePct >= 80 ? "success" : scorePct >= 50 ? "info" : "default";
  const matched = extractMatchedTerms(result.snippet || "", query);

  return (
    <Link href={href} className="block">
      <div className="result-card bg-surface border border-border p-5 rounded-xl hover:border-primary hover:shadow-md transition-all cursor-pointer group">
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
        <p className="text-body-md text-on-surface-variant mb-3 leading-relaxed line-clamp-3">
          {result.snippet ? highlight(result.snippet, query) : "无预览"}
        </p>
        {/* 相关性解释 */}
        <div className="flex items-center gap-1.5 mb-2 text-label-sm text-primary">
          <Icon name="auto_awesome" className="text-[14px]" />
          <span className="truncate">{explainRelevance(result, isMandol, query)}</span>
        </div>
        {/* 命中关键词标签 */}
        {matched.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mb-3">
            {matched.slice(0, 5).map((m) => (
              <span key={m} className="px-2 py-0.5 bg-yellow-100 text-amber-800 rounded text-label-sm border border-yellow-200">
                命中: {m}
              </span>
            ))}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-3">
          {result.track && <Pill variant="info" size="sm">{result.track}</Pill>}
          {result.memory_type && <Pill size="sm">{result.memory_type}</Pill>}
          <span className="ml-auto text-label-sm text-outline font-mono truncate">
            {result.rel_path}
          </span>
        </div>
      </div>
    </Link>
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
  const [showLowRelevance, setShowLowRelevance] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const isMandolStrategy = ["mandol", "entity", "event", "graph", "causal"].includes(strategy);

  // 计算每个结果的相关性分桶与归一化分数
  const processedResults = useMemo(() => {
    if (!results) return { high: [], low: [], total: 0, minScore: 0, threshold: 0 };
    const items = results.results.map((r) => {
      const raw = r.score || 0;
      // Mandol 分数通常 0-10，传统 0-1，统一归一化
      const norm = isMandolStrategy
        ? Math.min(1, raw / 10)
        : Math.min(1, raw);
      return { result: r, norm, raw };
    });
    // 按归一化分降序
    items.sort((a, b) => b.norm - a.norm);
    if (items.length === 0) {
      return { high: [], low: [], total: 0, minScore: 0, threshold: 0 };
    }
    // 自适应阈值：基于分数分布（gap-based）+ 最低数量保证
    //   1) 寻找最大「断崖」(相邻分差 > 均值差)，作为天然分界
    //   2) 至少保留前 3 条作为高相关
    //   3) 至少过滤掉 30% 的尾部低相关结果
    const n = items.length;
    const minKeep = Math.min(3, n);
    const maxDropRatio = 0.3; // 最多保留前 70% 作为高相关
    const maxKeep = Math.max(minKeep, Math.floor(n * (1 - maxDropRatio)));
    // 找最大 gap
    let bestGap = 0;
    let bestIdx = n;
    for (let i = 1; i < n; i++) {
      const gap = items[i - 1].norm - items[i].norm;
      // 跳过前 minKeep 条
      if (i < minKeep) continue;
      if (i > maxKeep) break;
      if (gap > bestGap) {
        bestGap = gap;
        bestIdx = i;
      }
    }
    // 阈值 = 第 bestIdx 条的分数（不含）
    let threshold = items[bestIdx].norm;
    // 保底：保证至少 3 条
    if (bestIdx < minKeep) {
      threshold = items[Math.min(minKeep, n) - 1].norm;
    }
    const high = items.filter((it) => it.norm >= threshold);
    const low = items.filter((it) => it.norm < threshold);
    const minScore = items[n - 1].norm;
    return { high, low, total: items.length, minScore, threshold };
  }, [results, isMandolStrategy]);

  const displayedResults = showLowRelevance
    ? [...processedResults.high, ...processedResults.low]
    : processedResults.high;

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
      limit: 10,
      use_rerank: isMandolStrategy || undefined,
    });
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doSearch(query, strategy);
  };

  const onStrategyChange = (s: Strategy) => {
    setStrategy(s);
    setShowLowRelevance(false);
    if (query.trim()) doSearch(query, s);
  };

  return (
    <AppShell title="记忆检索" subtitle="检索关键记忆信息">
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
                    title="清空"
                  >
                    <Icon name="close" className="text-[18px]" />
                  </button>
                )}
                <button
                  type="submit"
                  disabled={!query.trim() || isLoading}
                  className="px-4 py-1.5 bg-primary text-on-primary rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isLoading ? "搜索中..." : "查询"}
                </button>
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
                        search({
                          query,
                          strategy,
                          track: e.target.value || undefined,
                          limit: 10,
                          use_rerank: isMandolStrategy || undefined,
                        });
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
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-label-sm text-on-surface-variant">高相关:</span>
                      <span className="text-label-md font-bold text-success">
                        {processedResults.high.length}
                      </span>
                    </div>
                    {processedResults.low.length > 0 && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-label-sm text-on-surface-variant">低相关:</span>
                        <span className="text-label-md text-outline">
                          {processedResults.low.length}
                        </span>
                      </div>
                    )}
                    <div className="flex items-center gap-1.5">
                      <span className="text-label-sm text-on-surface-variant">总计:</span>
                      <span className="text-label-md font-bold text-on-surface">
                        {results.total} 条
                      </span>
                    </div>
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
                {/* 策略说明与统计 */}
                <div className="flex flex-wrap items-center justify-between gap-2 px-1 py-2 bg-surface-container-low rounded-lg border border-border">
                  <div className="flex items-center gap-2 px-2">
                    <Icon name="tips_and_updates" className="text-primary text-[18px]" />
                    <span className="text-label-md text-on-surface-variant">
                      当前策略：
                      <span className="font-bold text-primary ml-1">{STRATEGY_LABELS[strategy]}</span>
                      ，仅显示高相关结果
                    </span>
                  </div>
                  {processedResults.low.length > 0 && (
                    <button
                      onClick={() => setShowLowRelevance((v) => !v)}
                      className="text-label-sm px-3 py-1 mr-2 rounded text-on-surface-variant hover:bg-surface-container transition-colors"
                    >
                      {showLowRelevance
                        ? `收起低相关 (${processedResults.low.length})`
                        : `展开低相关 (${processedResults.low.length})`}
                    </button>
                  )}
                </div>

                {displayedResults.length === 0 ? (
                  <EmptyState
                    icon="filter_alt_off"
                    title="无高相关结果"
                    description={`${processedResults.low.length} 条结果相关性较低，已默认隐藏。点击"展开低相关"查看全部，或尝试其他关键词/策略。`}
                  />
                ) : (
                  displayedResults.map(({ result }, i) => (
                    <div key={result.uid || result.rel_path || i} className="space-y-1">
                      {/* 低相关结果分组分隔线 */}
                      {showLowRelevance && i === processedResults.high.length && processedResults.high.length > 0 && (
                        <div className="flex items-center gap-2 py-2">
                          <div className="flex-1 h-px bg-border" />
                          <span className="text-label-sm text-outline">以下为低相关结果</span>
                          <div className="flex-1 h-px bg-border" />
                        </div>
                      )}
                      <ResultCard
                        result={result}
                        query={query}
                        isMandol={isMandolStrategy}
                      />
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
