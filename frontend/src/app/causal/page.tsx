"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { api, ApiError } from "@/services/api";
import type { SubgraphResponse } from "@/types";

export default function CausalPage() {
  return (
    <Suspense fallback={<Loading label="加载中..." />}>
      <CausalContent />
    </Suspense>
  );
}

function CausalContent() {
  const searchParams = useSearchParams();
  const eventUid = searchParams.get("event");

  const [query, setQuery] = useState("");
  const [maxHops, setMaxHops] = useState(3);
  const [direction, setDirection] = useState<"forward" | "backward" | "both">("both");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SubgraphResponse | null>(null);

  useEffect(() => {
    if (eventUid) {
      setQuery(eventUid);
      doSearch(eventUid, maxHops, direction);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventUid]);

  const doSearch = async (q: string, hops: number, dir: "forward" | "backward" | "both") => {
    if (!q.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      // 使用图谱 BFS 扩展来追踪因果链
      // 方向决定使用哪种关系：forward=CAUSES, backward=CAUSED_BY, both=两者都用
      const relTypes = dir === "forward" ? ["CAUSES"] : dir === "backward" ? ["CAUSED_BY"] : ["CAUSES", "CAUSED_BY"];
      const data = await api.post<SubgraphResponse>("mandol/graph/bfs-expand", {
        seed_uids: [q],
        max_depth: hops,
        rel_types: relTypes,
        top_k: 20,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "追踪失败");
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    doSearch(query, maxHops, direction);
  };

  return (
    <AppShell title="因果链追踪" subtitle="追踪因果关系">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8">
          {/* 搜索表单 */}
          <div className="mb-6 bg-surface border border-border rounded-xl p-5">
            <form onSubmit={handleSearch} className="space-y-4">
              <div>
                <label className="block text-body-sm font-medium text-on-surface mb-2">查询事件 UID</label>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="输入事件 UID..."
                  className="w-full px-4 py-2.5 bg-surface-container-low border border-border rounded-lg focus:ring-2 focus:ring-primary outline-none text-body-md"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-body-sm font-medium text-on-surface mb-2">最大跳数</label>
                  <select
                    value={maxHops}
                    onChange={(e) => setMaxHops(Number(e.target.value))}
                    className="w-full px-4 py-2.5 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                  >
                    <option value={1}>1 跳</option>
                    <option value={2}>2 跳</option>
                    <option value={3}>3 跳</option>
                    <option value={4}>4 跳</option>
                    <option value={5}>5 跳</option>
                  </select>
                </div>

                <div>
                  <label className="block text-body-sm font-medium text-on-surface mb-2">方向</label>
                  <select
                    value={direction}
                    onChange={(e) => setDirection(e.target.value as "forward" | "backward" | "both")}
                    className="w-full px-4 py-2.5 bg-surface-container-low border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
                  >
                    <option value="both">双向</option>
                    <option value="forward">仅正向（导致）</option>
                    <option value="backward">仅反向（被导致）</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading || !query.trim()}
                className="w-full bg-primary text-on-primary py-2.5 rounded-lg font-bold text-body-md hover:opacity-90 disabled:opacity-50 transition-all flex items-center justify-center gap-2"
              >
                <Icon name="search" className="text-[18px]" />
                追踪因果链
              </button>
            </form>
          </div>

          {error && (
            <div className="bg-error/10 border border-error/20 text-error rounded-lg p-4 mb-6 flex items-center gap-2">
              <Icon name="error" filled />
              <span className="text-body-md">{error}</span>
            </div>
          )}

          {isLoading && <Loading label="追踪因果链中..." />}

          {!query && !isLoading && (
            <EmptyState
              icon="account_tree"
              title="开始追踪"
              description="输入事件 UID 来追踪其因果链。系统将沿 CAUSES / CAUSED_BY 关系进行 BFS 扩展。"
            />
          )}

          {/* 因果链可视化 */}
          {result && !isLoading && (
            <div className="space-y-4">
              {result.nodes.length === 0 ? (
                <EmptyState
                  icon="search_off"
                  title="未找到因果链"
                  description="未找到该事件的因果关系。请先执行记忆构建以提取事件和因果关系。"
                />
              ) : (
                <>
                  {/* 链统计 */}
                  <div className="bg-surface border border-border rounded-xl p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Icon name="timeline" className="text-primary text-[24px]" />
                        <div>
                          <h3 className="text-body-lg font-bold text-on-surface">因果链</h3>
                          <p className="text-body-sm text-on-surface-variant">
                            找到 {result.nodes.length} 个节点，{result.edges.length} 条关系
                          </p>
                        </div>
                      </div>
                      <Pill variant="info" size="md">
                        {direction === "both" ? "双向" : direction === "forward" ? "正向" : "反向"}
                      </Pill>
                    </div>
                  </div>

                  {/* 节点列表 */}
                  <div className="space-y-3">
                    {result.nodes.map((node, i) => (
                      <div key={node.uid} className="bg-surface border border-border rounded-xl p-5 hover:border-primary transition-all">
                        <div className="flex items-start gap-3 mb-3">
                          <div className="flex items-center justify-center w-8 h-8 bg-primary/10 text-primary rounded-full font-bold text-body-md">
                            {i + 1}
                          </div>
                          <div className="flex-1">
                            <h3 className="text-body-lg font-bold text-on-surface mb-1">
                              {node.name || node.uid}
                            </h3>
                            {node.text && (
                              <p className="text-body-md text-on-surface-variant">{node.text}</p>
                            )}
                          </div>
                          <Pill variant="info" size="sm">{node.type}</Pill>
                        </div>
                        <div className="ml-11 text-label-sm text-outline font-mono">
                          UID: {node.uid}
                        </div>

                        {i < result.nodes.length - 1 && (
                          <div className="ml-4 mt-3 flex items-center gap-2 text-outline">
                            <Icon name="arrow_downward" className="text-[20px]" />
                            <span className="text-label-sm">导致</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* 关系列表 */}
                  {result.edges.length > 0 && (
                    <div className="bg-surface border border-border rounded-xl p-5">
                      <h3 className="text-body-md font-bold text-on-surface mb-3">关系详情</h3>
                      <div className="space-y-2">
                        {result.edges.map((edge, i) => (
                          <div key={i} className="bg-surface-container-low rounded-lg p-3">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-body-sm text-on-surface truncate">{edge.source}</span>
                              <span className="px-2 py-0.5 bg-secondary-container text-on-secondary-container rounded text-label-sm whitespace-nowrap">
                                {edge.relationship}
                              </span>
                              <Icon name="arrow_forward" className="text-on-surface-variant text-[14px]" />
                              <span className="text-body-sm text-on-surface truncate">{edge.target}</span>
                            </div>
                            {edge.confidence < 1.0 && (
                              <p className="text-label-sm text-on-surface-variant mt-1">
                                置信度: {(edge.confidence * 100).toFixed(0)}%
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
