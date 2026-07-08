"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMandol } from "@/hooks/useMandol";
import { api, ApiError } from "@/services/api";
import type { SubgraphResponse, TraceResponse } from "@/types";

export default function GraphPage() {
  const { subgraph, traceResult, getEntitySubgraph, traceEvidence, traceCoref, isLoading } = useMandol();
  const [query, setQuery] = useState("");
  const [maxDepth, setMaxDepth] = useState(2);
  const [topK, setTopK] = useState(10);
  const [activeTab, setActiveTab] = useState<"subgraph" | "trace" | "coref">("subgraph");
  const [traceUid, setTraceUid] = useState("");

  const handleSearch = async () => {
    if (!query.trim()) return;
    await getEntitySubgraph(query.trim(), maxDepth, topK);
  };

  const handleTrace = async (type: "evidence" | "coref") => {
    if (!traceUid.trim()) return;
    if (type === "evidence") {
      await traceEvidence(traceUid.trim(), maxDepth, topK);
    } else {
      await traceCoref(traceUid.trim(), maxDepth, topK);
    }
  };

  return (
    <AppShell title="知识图谱" subtitle="图谱遍历、子图查询与溯源追踪">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">
          {/* 标签切换 */}
          <div className="flex items-center gap-2 border-b border-border">
            {[
              { key: "subgraph" as const, label: "实体子图", icon: "account_tree" },
              { key: "trace" as const, label: "溯源追踪", icon: "timeline" },
              { key: "coref" as const, label: "共指追踪", icon: "merge_type" },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={[
                  "flex items-center gap-2 px-4 py-2 text-body-md font-medium transition-colors border-b-2",
                  activeTab === tab.key
                    ? "border-primary text-primary"
                    : "border-transparent text-on-surface-variant hover:text-on-surface",
                ].join(" ")}
              >
                <Icon name={tab.icon} className="text-[18px]" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* 参数控制 */}
          <section className="bg-surface border border-border rounded-xl p-5">
            <div className="flex items-center gap-4 flex-wrap">
              {activeTab === "subgraph" ? (
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="输入查询文本（如实体名称）"
                  className="flex-1 min-w-[200px] px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                />
              ) : (
                <input
                  type="text"
                  value={traceUid}
                  onChange={(e) => setTraceUid(e.target.value)}
                  placeholder="输入单元 UID"
                  className="flex-1 min-w-[200px] px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
                  onKeyDown={(e) => e.key === "Enter" && handleTrace(activeTab === "trace" ? "evidence" : "coref")}
                />
              )}
              <label className="flex items-center gap-1">
                <span className="text-body-sm text-on-surface-variant">深度</span>
                <input
                  type="number"
                  value={maxDepth}
                  onChange={(e) => setMaxDepth(Number(e.target.value))}
                  min={1}
                  max={5}
                  className="w-16 px-2 py-1 rounded border border-border bg-surface-container-low text-on-surface"
                />
              </label>
              <label className="flex items-center gap-1">
                <span className="text-body-sm text-on-surface-variant">TopK</span>
                <input
                  type="number"
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  min={1}
                  max={50}
                  className="w-16 px-2 py-1 rounded border border-border bg-surface-container-low text-on-surface"
                />
              </label>
              <button
                onClick={() =>
                  activeTab === "subgraph"
                    ? handleSearch()
                    : handleTrace(activeTab === "trace" ? "evidence" : "coref")
                }
                disabled={isLoading}
                className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:bg-opacity-90 disabled:opacity-50"
              >
                {isLoading ? "查询中..." : "查询"}
              </button>
            </div>
          </section>

          {/* 结果展示 */}
          {isLoading && <Loading size="md" label="加载中..." />}

          {!isLoading && activeTab === "subgraph" && subgraph && (
            <SubgraphView data={subgraph} />
          )}

          {!isLoading && activeTab !== "subgraph" && traceResult && (
            <TraceView data={traceResult} type={activeTab} />
          )}

          {!isLoading && !subgraph && !traceResult && activeTab === "subgraph" && (
            <EmptyState
              icon="account_tree"
              title="知识图谱"
              description="输入查询文本，探索实体间的语义关系网络。"
            />
          )}
        </div>
      </div>
    </AppShell>
  );
}

function SubgraphView({ data }: { data: SubgraphResponse }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 节点列表 */}
        <section className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-body-md font-bold text-on-surface mb-3">
            节点 ({data.nodes.length})
          </h3>
          <div className="space-y-2 max-h-96 overflow-y-auto custom-scrollbar">
            {data.nodes.map((node) => (
              <div key={node.uid} className="bg-surface-container-low rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2 py-0.5 bg-primary-fixed text-primary rounded text-label-sm">
                    {node.type}
                  </span>
                  <span className="text-body-sm font-medium text-on-surface truncate">{node.name || node.uid}</span>
                </div>
                {node.text && (
                  <p className="text-body-sm text-on-surface-variant line-clamp-2">{node.text}</p>
                )}
              </div>
            ))}
            {data.nodes.length === 0 && (
              <p className="text-body-sm text-on-surface-variant">无节点</p>
            )}
          </div>
        </section>

        {/* 边列表 */}
        <section className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-body-md font-bold text-on-surface mb-3">
            关系边 ({data.edges.length})
          </h3>
          <div className="space-y-2 max-h-96 overflow-y-auto custom-scrollbar">
            {data.edges.map((edge, i) => (
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
                  <p className="text-label-sm text-on-surface-variant mt-1">置信度: {edge.confidence.toFixed(3)}</p>
                )}
              </div>
            ))}
            {data.edges.length === 0 && (
              <p className="text-body-sm text-on-surface-variant">无关系边</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function TraceView({ data, type }: { data: TraceResponse; type: "trace" | "coref" }) {
  return (
    <div className="space-y-4">
      <section className="bg-surface border border-border rounded-xl p-5">
        <h3 className="text-body-md font-bold text-on-surface mb-3">
          {type === "trace" ? "溯源链" : "共指链"} ({data.chain.length})
        </h3>
        <div className="space-y-3">
          {data.chain.map((step, i) => (
            <div key={i} className="bg-surface-container-low rounded-lg p-3 flex items-start gap-3">
              <span className="w-6 h-6 rounded-full bg-primary text-on-primary flex items-center justify-center text-label-sm font-bold flex-shrink-0">
                {i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <pre className="text-body-sm text-on-surface whitespace-pre-wrap break-words">
                  {JSON.stringify(step, null, 2)}
                </pre>
              </div>
            </div>
          ))}
          {data.chain.length === 0 && (
            <p className="text-body-sm text-on-surface-variant">无追踪结果</p>
          )}
        </div>
      </section>
      {data.summary && (
        <section className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-body-md font-bold text-on-surface mb-2">摘要</h3>
          <pre className="text-body-sm text-on-surface whitespace-pre-wrap">
            {JSON.stringify(data.summary, null, 2)}
          </pre>
        </section>
      )}
    </div>
  );
}
