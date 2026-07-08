"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMandol } from "@/hooks/useMandol";
import type {
  SubgraphResponse,
  TraceResponse,
  Neo4jSubgraph,
  RelationshipInfo,
} from "@/types";

type Tab = "subgraph" | "neo4j" | "trace" | "coref" | "relationships";

export default function GraphPage() {
  const {
    subgraph,
    traceResult,
    neo4jSubgraph,
    externalStatus,
    relationships,
    getEntitySubgraph,
    traceEvidence,
    traceCoref,
    getNeo4jSubgraph,
    getExternalStatus,
    listRelationships,
    isLoading,
  } = useMandol();

  const [query, setQuery] = useState("");
  const [maxDepth, setMaxDepth] = useState(2);
  const [topK, setTopK] = useState(10);
  const [activeTab, setActiveTab] = useState<Tab>("subgraph");
  const [traceUid, setTraceUid] = useState("");
  const [relUid, setRelUid] = useState("");
  const [relDirection, setRelDirection] = useState<"in" | "out" | "all">("all");
  const [relErr, setRelErr] = useState<string | null>(null);

  useEffect(() => {
    getExternalStatus();
  }, [getExternalStatus]);

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

  const handleNeo4j = async () => {
    await getNeo4jSubgraph(undefined, 200);
  };

  const handleListRel = async () => {
    setRelErr(null);
    if (!relUid.trim()) {
      setRelErr("请输入单元 UID");
      return;
    }
    await listRelationships(relUid.trim(), relDirection);
  };

  return (
    <AppShell title="知识图谱" subtitle="图谱遍历 · Neo4j 子图 · 关系管理 · 溯源">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">

          {/* 顶部状态条 */}
          {externalStatus && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <Pill variant={externalStatus.neo4j.available ? "success" : "default"} size="md">
                <Icon name="hub" className="text-[14px]" />
                Neo4j · {externalStatus.neo4j.available ? `${externalStatus.neo4j.nodes} 节点 / ${externalStatus.neo4j.edges} 边` : "离线"}
              </Pill>
              <Pill variant={externalStatus.milvus.available ? "success" : "default"} size="md">
                <Icon name="database" className="text-[14px]" />
                Milvus · {externalStatus.milvus.available ? `${externalStatus.milvus.unit_count} 单元` : "离线"}
              </Pill>
              <Pill variant="info" size="md">
                <Icon name="merge_type" className="text-[14px]" />
                关系类型: {externalStatus.neo4j.rel_types.slice(0, 4).join(", ") || "—"}
              </Pill>
            </div>
          )}

          {/* 标签切换 */}
          <div className="flex items-center gap-1 border-b border-border overflow-x-auto">
            {[
              { key: "subgraph" as const, label: "实体子图", icon: "account_tree" },
              { key: "neo4j" as const, label: "Neo4j 全图", icon: "hub" },
              { key: "relationships" as const, label: "关系管理", icon: "link" },
              { key: "trace" as const, label: "溯源追踪", icon: "timeline" },
              { key: "coref" as const, label: "共指追踪", icon: "merge_type" },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={[
                  "flex items-center gap-2 px-4 py-2 text-body-md font-medium transition-colors border-b-2 whitespace-nowrap",
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
            {activeTab === "subgraph" && (
              <div className="flex items-center gap-4 flex-wrap">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="输入查询文本（如实体名称、关键词）"
                  className="flex-1 min-w-[200px] px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                />
                <RangeField label="深度" value={maxDepth} onChange={setMaxDepth} min={1} max={5} />
                <RangeField label="TopK" value={topK} onChange={setTopK} min={1} max={50} />
                <button
                  onClick={handleSearch}
                  disabled={isLoading}
                  className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:opacity-90 disabled:opacity-50"
                >
                  {isLoading ? "查询中..." : "查询"}
                </button>
              </div>
            )}

            {activeTab === "neo4j" && (
              <div className="flex items-center gap-4 flex-wrap">
                <p className="text-body-md text-on-surface-variant flex-1">
                  直接从 Neo4j 图数据库读取实际节点与关系（用于图谱可视化）
                </p>
                <RangeField label="上限" value={topK * 20} onChange={(v) => setTopK(Math.max(1, Math.floor(v / 20)))} min={20} max={2000} step={20} />
                <button
                  onClick={handleNeo4j}
                  disabled={isLoading}
                  className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
                >
                  <Icon name="download" className="text-[16px]" />
                  {isLoading ? "读取中..." : "从 Neo4j 读取"}
                </button>
              </div>
            )}

            {activeTab === "relationships" && (
              <div className="flex items-center gap-4 flex-wrap">
                <input
                  type="text"
                  value={relUid}
                  onChange={(e) => setRelUid(e.target.value)}
                  placeholder="输入单元 UID"
                  className="flex-1 min-w-[200px] px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
                />
                <select
                  value={relDirection}
                  onChange={(e) => setRelDirection(e.target.value as "in" | "out" | "all")}
                  className="px-3 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface"
                >
                  <option value="all">全部方向</option>
                  <option value="out">出向</option>
                  <option value="in">入向</option>
                </select>
                <button
                  onClick={handleListRel}
                  disabled={isLoading}
                  className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:opacity-90 disabled:opacity-50"
                >
                  {isLoading ? "查询中..." : "查询关系"}
                </button>
              </div>
            )}

            {(activeTab === "trace" || activeTab === "coref") && (
              <div className="flex items-center gap-4 flex-wrap">
                <input
                  type="text"
                  value={traceUid}
                  onChange={(e) => setTraceUid(e.target.value)}
                  placeholder="输入单元 UID"
                  className="flex-1 min-w-[200px] px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
                  onKeyDown={(e) => e.key === "Enter" && handleTrace(activeTab === "trace" ? "evidence" : "coref")}
                />
                <RangeField label="深度" value={maxDepth} onChange={setMaxDepth} min={1} max={5} />
                <RangeField label="TopK" value={topK} onChange={setTopK} min={1} max={50} />
                <button
                  onClick={() => handleTrace(activeTab === "trace" ? "evidence" : "coref")}
                  disabled={isLoading}
                  className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:opacity-90 disabled:opacity-50"
                >
                  {isLoading ? "追踪中..." : "追踪"}
                </button>
              </div>
            )}
          </section>

          {relErr && (
            <div className="bg-error/10 border border-error/20 text-error rounded-lg p-3 flex items-center gap-2">
              <Icon name="error" filled />
              <span className="text-body-md">{relErr}</span>
            </div>
          )}

          {isLoading && <Loading size="md" label="加载中..." />}

          {/* 实体子图 */}
          {!isLoading && activeTab === "subgraph" && subgraph && <SubgraphView data={subgraph} />}

          {/* Neo4j 全图 */}
          {!isLoading && activeTab === "neo4j" && neo4jSubgraph && <Neo4jView data={neo4jSubgraph} />}

          {/* 关系管理 */}
          {!isLoading && activeTab === "relationships" && (
            <RelationshipView rels={relationships} />
          )}

          {/* 溯源 */}
          {!isLoading && (activeTab === "trace" || activeTab === "coref") && traceResult && (
            <TraceView data={traceResult} type={activeTab} />
          )}

          {/* 空状态 */}
          {!isLoading && activeTab === "subgraph" && !subgraph && (
            <EmptyState
              icon="account_tree"
              title="实体子图"
              description="输入查询文本，基于语义检索探索实体关系网络。"
            />
          )}
          {!isLoading && activeTab === "neo4j" && !neo4jSubgraph && (
            <EmptyState
              icon="hub"
              title="Neo4j 图数据库"
              description="点击「从 Neo4j 读取」直接查看图数据库中的实际节点和关系。"
            />
          )}
          {!isLoading && activeTab === "relationships" && relationships.length === 0 && (
            <EmptyState
              icon="link"
              title="关系管理"
              description="输入单元 UID 查询与其相关的全部关系边。"
            />
          )}
          {!isLoading && (activeTab === "trace" || activeTab === "coref") && !traceResult && (
            <EmptyState
              icon={activeTab === "trace" ? "timeline" : "merge_type"}
              title={activeTab === "trace" ? "溯源追踪" : "共指追踪"}
              description="输入 UID 追溯记忆的来源链条或共指关系链。"
            />
          )}
        </div>
      </div>
    </AppShell>
  );
}

function RangeField({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
}) {
  return (
    <label className="flex items-center gap-1">
      <span className="text-body-sm text-on-surface-variant">{label}</span>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        min={min}
        max={max}
        step={step}
        className="w-20 px-2 py-1 rounded border border-border bg-surface-container-low text-on-surface"
      />
    </label>
  );
}

function SubgraphView({ data }: { data: SubgraphResponse }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <section className="bg-surface border border-border rounded-xl p-5">
        <h3 className="text-body-md font-bold text-on-surface mb-3">节点 ({data.nodes.length})</h3>
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
          {data.nodes.length === 0 && <p className="text-body-sm text-on-surface-variant">无节点</p>}
        </div>
      </section>
      <section className="bg-surface border border-border rounded-xl p-5">
        <h3 className="text-body-md font-bold text-on-surface mb-3">关系边 ({data.edges.length})</h3>
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
          {data.edges.length === 0 && <p className="text-body-sm text-on-surface-variant">无关系边</p>}
        </div>
      </section>
    </div>
  );
}

function Neo4jView({ data }: { data: Neo4jSubgraph }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 text-body-sm text-on-surface-variant flex-wrap">
        <Pill size="sm" variant="info">Neo4j 直读</Pill>
        <span>{data.nodes.length} 节点 / {data.edges.length} 边</span>
        {data.center && <span>· 中心节点 {data.center}</span>}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-body-md font-bold text-on-surface mb-3">图节点</h3>
          <div className="space-y-2 max-h-[28rem] overflow-y-auto custom-scrollbar">
            {data.nodes.map((node) => {
              const uidStr = String(node.uid || "");
              const labels = (node.labels || []).filter((l) => l !== "Resource");
              // uid 前缀：doc:/entity:/event:/summary: 等用于回退显示
              const prefix = uidStr.includes(":") ? uidStr.split(":")[0] : "";
              const allLabels = labels.length > 0 ? labels : prefix ? [prefix] : [];
              const name =
                (node.props?.name as string) ||
                (node.props?.title as string) ||
                (node.props?.text as string)?.slice(0, 60) ||
                uidStr;
              return (
                <div key={uidStr} className="bg-surface-container-low rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    {allLabels.map((l) => (
                      <span key={l} className="px-2 py-0.5 bg-primary-fixed text-primary rounded text-label-sm">
                        {l}
                      </span>
                    ))}
                    <span className="text-body-sm font-medium text-on-surface truncate" title={name}>{name}</span>
                  </div>
                  <p className="text-label-sm text-on-surface-variant font-mono truncate">
                    uid: {uidStr || "—"}
                  </p>
                </div>
              );
            })}
            {data.nodes.length === 0 && <p className="text-body-sm text-on-surface-variant">无节点</p>}
          </div>
        </section>
        <section className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-body-md font-bold text-on-surface mb-3">图关系</h3>
          <div className="space-y-2 max-h-[28rem] overflow-y-auto custom-scrollbar">
            {data.edges.map((edge, i) => {
              const score = (edge.props?.score as number) ?? (edge.props?.weight as number);
              return (
                <div key={i} className="bg-surface-container-low rounded-lg p-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-body-sm text-on-surface truncate max-w-[40%]">{String(edge.s || "—")}</span>
                    <span className="px-2 py-0.5 bg-secondary-container text-on-secondary-container rounded text-label-sm whitespace-nowrap">
                      {edge.type || "RELATED"}
                    </span>
                    <Icon name="arrow_forward" className="text-on-surface-variant text-[14px]" />
                    <span className="text-body-sm text-on-surface truncate max-w-[40%]">{String(edge.t || "—")}</span>
                  </div>
                  {score != null && (
                    <p className="text-label-sm text-on-surface-variant mt-1">权重: {Number(score).toFixed(3)}</p>
                  )}
                </div>
              );
            })}
            {data.edges.length === 0 && <p className="text-body-sm text-on-surface-variant">无关系</p>}
          </div>
        </section>
      </div>
    </div>
  );
}

function RelationshipView({ rels }: { rels: RelationshipInfo[] }) {
  if (rels.length === 0) {
    return (
      <EmptyState
        icon="link_off"
        title="暂无关系"
        description="该单元尚未建立任何关系。"
      />
    );
  }
  return (
    <section className="bg-surface border border-border rounded-xl p-5">
      <h3 className="text-body-md font-bold text-on-surface mb-3">关系列表 ({rels.length})</h3>
      <div className="space-y-2">
        {rels.map((r, i) => (
          <div key={i} className="bg-surface-container-low rounded-lg p-3 flex items-center gap-3 flex-wrap">
            <span className="text-body-sm text-on-surface font-mono truncate">{r.source}</span>
            <span className="px-2 py-0.5 bg-secondary-container text-on-secondary-container rounded text-label-sm whitespace-nowrap">
              {r.rel_type}
            </span>
            <Icon name="arrow_forward" className="text-on-surface-variant text-[14px]" />
            <span className="text-body-sm text-on-surface font-mono truncate">{r.target}</span>
            {Object.keys(r.properties || {}).length > 0 && (
              <details className="ml-auto text-label-sm text-on-surface-variant">
                <summary className="cursor-pointer">属性</summary>
                <pre className="mt-1 text-label-sm bg-surface-container p-2 rounded">
                  {JSON.stringify(r.properties, null, 2)}
                </pre>
              </details>
            )}
          </div>
        ))}
      </div>
    </section>
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
          {data.chain.length === 0 && <p className="text-body-sm text-on-surface-variant">无追踪结果</p>}
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
