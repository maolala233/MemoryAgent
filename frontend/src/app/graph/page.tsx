"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { ForceGraph, GraphNode, GraphEdge } from "@/components/graph/ForceGraph";
import { EntitySearchInput, UnitHit } from "@/components/graph/EntitySearchInput";
import { useMandol } from "@/hooks/useMandol";
import type {
  SubgraphResponse,
  TraceResponse,
  Neo4jSubgraph,
  RelationshipInfo,
} from "@/types";

type Tab = "subgraph" | "neo4j" | "relationships" | "trace" | "coref";

export default function GraphPage() {
  const router = useRouter();
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

  // subgraph tab
  const [query, setQuery] = useState("");
  const [maxDepth, setMaxDepth] = useState(2);
  const [topK, setTopK] = useState(10);
  // neo4j tab — 关键词 + 中心 uid（可来自 EntitySearchInput）
  const [neo4jCenterUid, setNeo4jCenterUid] = useState("");
  const [neo4jKeyword, setNeo4jKeyword] = useState("");
  const [neo4jLimit, setNeo4jLimit] = useState(200);
  // relationships tab
  const [relUid, setRelUid] = useState("");
  const [relDirection, setRelDirection] = useState<"in" | "out" | "all">("all");
  const [relErr, setRelErr] = useState<string | null>(null);
  // trace tab
  const [traceUid, setTraceUid] = useState("");

  const [activeTab, setActiveTab] = useState<Tab>("subgraph");

  // 当前选中的节点/边（用于右侧详情面板）
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);

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
    const kw = neo4jKeyword.trim();
    const uid = neo4jCenterUid.trim();
    if (kw) {
      await getNeo4jSubgraph(undefined, neo4jLimit, kw);
    } else if (uid) {
      await getNeo4jSubgraph(uid, neo4jLimit, undefined);
    } else {
      await getNeo4jSubgraph(undefined, neo4jLimit, undefined);
    }
  };

  const handleListRel = async () => {
    setRelErr(null);
    if (!relUid.trim()) {
      setRelErr("请先在上方输入单元 UID 或用关键词搜索锁定节点");
      return;
    }
    await listRelationships(relUid.trim(), relDirection);
  };

  return (
    <AppShell title="知识图谱" subtitle="图谱遍历 · Neo4j 可视化 · 关系管理 · 溯源追踪">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">

          {/* 顶部状态条 */}
          {externalStatus && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <Pill variant={externalStatus.neo4j.available ? "success" : "default"} size="md">
                <Icon name="hub" className="text-[14px]" />
                Neo4j · {externalStatus.neo4j.available
                  ? `${externalStatus.neo4j.nodes} 节点 / ${externalStatus.neo4j.edges} 边`
                  : "离线"}
              </Pill>
              <Pill variant={externalStatus.milvus.available ? "success" : "default"} size="md">
                <Icon name="database" className="text-[14px]" />
                Milvus · {externalStatus.milvus.available
                  ? `${externalStatus.milvus.unit_count} 单元`
                  : "离线"}
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
              { key: "neo4j" as const, label: "Neo4j 图谱", icon: "hub" },
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
          <section className="bg-surface border border-border rounded-xl p-5 space-y-3">
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
                  className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
                >
                  <Icon name="search" className="text-[16px]" />
                  {isLoading ? "查询中..." : "查询"}
                </button>
              </div>
            )}

            {activeTab === "neo4j" && (
              <div className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <EntitySearchInput
                    label="🔎 关键词搜索（小白入口，不用记 UID）"
                    value={neo4jCenterUid}
                    onChange={(uid) => setNeo4jCenterUid(uid)}
                    placeholder="比如：科创e贷、信贷、年度报告…"
                  />
                  <div className="flex flex-col">
                    <label className="block text-label-md text-on-surface-variant mb-1">
                      或直接指定 UID（高级）
                    </label>
                    <input
                      type="text"
                      value={neo4jCenterUid}
                      onChange={(e) => setNeo4jCenterUid(e.target.value)}
                      placeholder="例：doc:imports/xxx.md:chunk:3"
                      className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface font-mono text-label-md focus:outline-none focus:border-primary"
                    />
                  </div>
                </div>
                <div className="flex items-center gap-4 flex-wrap">
                  <RangeField
                    label="节点上限"
                    value={neo4jLimit}
                    onChange={setNeo4jLimit}
                    min={20}
                    max={1000}
                    step={20}
                  />
                  <button
                    onClick={handleNeo4j}
                    disabled={isLoading}
                    className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
                  >
                    <Icon name="hub" className="text-[16px]" />
                    {isLoading ? "读取中..." : neo4jCenterUid ? "可视化该节点子图" : "读取 Neo4j 全图"}
                  </button>
                  {(neo4jCenterUid || neo4jKeyword) && (
                    <button
                      onClick={() => {
                        setNeo4jCenterUid("");
                        setNeo4jKeyword("");
                      }}
                      className="px-3 py-2 text-body-sm text-on-surface-variant hover:text-on-surface"
                    >
                      清空
                    </button>
                  )}
                </div>
                <p className="text-label-sm text-on-surface-variant">
                  💡 提示：上方搜索会调用 <code className="font-mono">/api/mandol/units?q=…</code>{" "}
                  做关键词模糊匹配，选中条目后点击按钮即可可视化该单元在 Neo4j 中的子图。
                </p>
              </div>
            )}

            {activeTab === "relationships" && (
              <div className="space-y-3">
                <EntitySearchInput
                  label="🔎 关键词搜索（小白入口）"
                  value={relUid}
                  onChange={(uid) => setRelUid(uid)}
                  placeholder="比如：信贷产品、审批流程…"
                />
                <div className="flex items-center gap-4 flex-wrap">
                  <span className="text-body-sm text-on-surface-variant">或直接输入 UID：</span>
                  <input
                    type="text"
                    value={relUid}
                    onChange={(e) => setRelUid(e.target.value)}
                    placeholder="单元 UID"
                    className="flex-1 min-w-[200px] px-3 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface font-mono text-label-md"
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
              </div>
            )}

            {(activeTab === "trace" || activeTab === "coref") && (
              <div className="space-y-3">
                <EntitySearchInput
                  label="🔎 关键词搜索（小白入口）"
                  value={traceUid}
                  onChange={(uid) => setTraceUid(uid)}
                  placeholder="比如：待办任务、授信审批…"
                />
                <div className="flex items-center gap-4 flex-wrap">
                  <span className="text-body-sm text-on-surface-variant">或直接输入 UID：</span>
                  <input
                    type="text"
                    value={traceUid}
                    onChange={(e) => setTraceUid(e.target.value)}
                    placeholder="单元 UID"
                    className="flex-1 min-w-[200px] px-3 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface font-mono text-label-md"
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

          {/* 实体子图（力导向可视化） */}
          {!isLoading && activeTab === "subgraph" && subgraph && (
            <SubgraphGraphView data={subgraph} onNodeClick={setSelectedNode} />
          )}

          {/* Neo4j 图谱可视化 */}
          {!isLoading && activeTab === "neo4j" && neo4jSubgraph && (
            <Neo4jGraphView
              data={neo4jSubgraph}
              onNodeClick={setSelectedNode}
              onEdgeClick={setSelectedEdge}
              selectedNodeId={selectedNode?.id}
            />
          )}

          {/* 关系管理 */}
          {!isLoading && activeTab === "relationships" && (
            <RelationshipView rels={relationships} />
          )}

          {/* 溯源 / 共指 */}
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
              description="在搜索框输入关键词（如：科创e贷、信贷），选中条目后点击按钮可视化节点子图。也可以留空读取全图。"
            />
          )}
          {!isLoading && activeTab === "relationships" && relationships.length === 0 && (
            <EmptyState
              icon="link"
              title="关系管理"
              description="用上方关键词搜索找到节点，再查询与其相关的全部关系边。"
            />
          )}
          {!isLoading && (activeTab === "trace" || activeTab === "coref") && !traceResult && (
            <EmptyState
              icon={activeTab === "trace" ? "timeline" : "merge_type"}
              title={activeTab === "trace" ? "溯源追踪" : "共指追踪"}
              description="用关键词搜索找到节点，再追溯记忆的来源链条或共指关系链。"
            />
          )}

          {/* 选中节点 / 边详情 */}
          {selectedNode && (
            <NodeDetailPanel
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
              onJumpToSubgraph={(uid) => {
                setNeo4jCenterUid(uid);
                setActiveTab("neo4j");
              }}
            />
          )}
          {selectedEdge && (
            <EdgeDetailPanel edge={selectedEdge} onClose={() => setSelectedEdge(null)} />
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

/* ------------------------------------------------------------------ */
/*  实体子图（Milvus 检索结果）：力导向可视化                          */
/* ------------------------------------------------------------------ */
function SubgraphGraphView({
  data,
  onNodeClick,
}: {
  data: SubgraphResponse;
  onNodeClick: (n: GraphNode) => void;
}) {
  const { graphNodes, graphEdges } = useMemo(() => {
    const labelOfType = (t?: string): string => {
      const lower = (t || "").toLowerCase();
      if (lower.includes("entity")) return "Entity";
      if (lower.includes("doc")) return "Document";
      if (lower.includes("event")) return "Event";
      if (lower.includes("summary")) return "Summary";
      return lower || "Entity";
    };
    const ns: GraphNode[] = data.nodes.map((n) => ({
      id: n.uid,
      label: n.name || n.uid.split(":").pop() || n.uid,
      group: labelOfType(n.type),
    }));
    const es: GraphEdge[] = data.edges.map((e, i) => ({
      id: `${e.source}->${e.target}-${i}`,
      source: e.source,
      target: e.target,
      label: e.relationship,
    }));
    return { graphNodes: ns, graphEdges: es };
  }, [data]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-body-sm text-on-surface-variant flex-wrap">
        <Pill size="sm" variant="info">实体子图</Pill>
        <span>{data.nodes.length} 节点 / {data.edges.length} 边</span>
        <span className="ml-auto text-label-sm">💡 可拖拽节点、滚轮缩放、点击节点查看详情</span>
      </div>
      <ForceGraph nodes={graphNodes} edges={graphEdges} onNodeClick={onNodeClick} height={560} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Neo4j 直读：力导向可视化                                           */
/* ------------------------------------------------------------------ */
function Neo4jGraphView({
  data,
  onNodeClick,
  onEdgeClick,
  selectedNodeId,
}: {
  data: Neo4jSubgraph;
  onNodeClick: (n: GraphNode) => void;
  onEdgeClick: (e: GraphEdge) => void;
  selectedNodeId?: string;
}) {
  const { graphNodes, graphEdges } = useMemo(() => {
    const ns: GraphNode[] = data.nodes.map((node) => {
      const uidStr = String(node.uid || "");
      const labels = (node.labels || []).filter((l) => l !== "Resource");
      const prefix = uidStr.includes(":") ? uidStr.split(":")[0] : "";
      const allLabels = labels.length > 0 ? labels : prefix ? [prefix] : [];
      const display =
        (node.props?.name as string) ||
        (node.props?.title as string) ||
        (node.props?.text as string)?.slice(0, 60) ||
        uidStr.split(":").pop() ||
        uidStr;
      return {
        id: uidStr,
        label: display,
        group: allLabels[0] || "default",
        color: undefined,
      };
    });
    const es: GraphEdge[] = data.edges.map((edge, i) => ({
      id: edge.id ? String(edge.id) : `${edge.s}-${edge.t}-${i}`,
      source: String(edge.s),
      target: String(edge.t),
      label: edge.type || "RELATED",
    }));
    return { graphNodes: ns, graphEdges: es };
  }, [data]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-body-sm text-on-surface-variant flex-wrap">
        <Pill size="sm" variant="info">Neo4j 直读</Pill>
        <span>{data.nodes.length} 节点 / {data.edges.length} 边</span>
        {data.center && <span>· 中心 {data.center}</span>}
        <span className="ml-auto text-label-sm">
          💡 拖拽节点布局、滚轮缩放、空白处平移、点击节点/关系查看详情
        </span>
      </div>
      <ForceGraph
        nodes={graphNodes}
        edges={graphEdges}
        centerId={selectedNodeId || (data.center ? String(data.center) : undefined)}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        height={620}
      />
      {/* 兜底：节点列表（小屏时辅助查看） */}
      <details className="bg-surface border border-border rounded-xl p-3">
        <summary className="cursor-pointer text-body-sm text-on-surface-variant select-none">
          📋 节点列表（{data.nodes.length}）
        </summary>
        <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 max-h-72 overflow-y-auto custom-scrollbar">
          {data.nodes.slice(0, 100).map((node) => {
            const uidStr = String(node.uid || "");
            const name =
              (node.props?.name as string) ||
              (node.props?.title as string) ||
              uidStr.split(":").pop() ||
              uidStr;
            return (
              <button
                key={uidStr}
                onClick={() => onNodeClick({
                  id: uidStr,
                  label: name,
                  group: (node.labels || [])[0] || "default",
                })}
                className="text-left bg-surface-container-low rounded p-2 hover:bg-primary/8"
              >
                <div className="text-body-sm text-on-surface truncate">{name}</div>
                <div className="text-label-sm text-on-surface-variant font-mono truncate">
                  {uidStr}
                </div>
              </button>
            );
          })}
        </div>
      </details>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  节点详情面板                                                       */
/* ------------------------------------------------------------------ */
function NodeDetailPanel({
  node,
  onClose,
  onJumpToSubgraph,
}: {
  node: GraphNode;
  onClose: () => void;
  onJumpToSubgraph: (uid: string) => void;
}) {
  const router = useRouter();
  const isUidLike = typeof node.id === "string" && node.id.includes(":");
  return (
    <aside className="fixed right-4 top-20 z-30 w-80 max-w-[90vw] bg-surface border border-border rounded-xl shadow-2xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-label-sm text-on-surface-variant">节点详情</div>
          <h3 className="text-body-md font-bold text-on-surface truncate" title={node.label}>
            {node.label}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded hover:bg-surface-container-low text-on-surface-variant flex items-center justify-center flex-shrink-0"
        >
          <Icon name="close" className="text-[16px]" />
        </button>
      </div>
      <div className="space-y-1.5">
        <DetailRow label="UID" value={node.id} mono />
        {node.group && <DetailRow label="分组" value={node.group} />}
      </div>
      <div className="flex flex-col gap-2 pt-1">
        {isUidLike && (
          <button
            onClick={() => router.push(`/entity/${encodeURIComponent(node.id)}`)}
            className="w-full bg-primary text-on-primary px-3 py-2 rounded-lg text-body-sm font-medium hover:opacity-90 flex items-center justify-center gap-1"
          >
            <Icon name="open_in_new" className="text-[16px]" />
            查看完整详情
          </button>
        )}
        <button
          onClick={() => onJumpToSubgraph(node.id)}
          className="w-full bg-secondary text-on-secondary px-3 py-2 rounded-lg text-body-sm font-medium hover:opacity-90 flex items-center justify-center gap-1"
        >
          <Icon name="hub" className="text-[16px]" />
          以此节点为中心可视化子图
        </button>
        <button
          onClick={() => navigator.clipboard?.writeText(node.id)}
          className="w-full bg-surface-container-low text-on-surface px-3 py-2 rounded-lg text-body-sm hover:bg-surface-container flex items-center justify-center gap-1"
        >
          <Icon name="content_copy" className="text-[16px]" />
          复制 UID
        </button>
      </div>
    </aside>
  );
}

function DetailRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start gap-2 text-label-md">
      <span className="text-on-surface-variant flex-shrink-0 w-14">{label}</span>
      <span
        className={`text-on-surface break-all ${mono ? "font-mono text-label-sm" : ""}`}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  边详情面板                                                         */
/* ------------------------------------------------------------------ */
function EdgeDetailPanel({
  edge,
  onClose,
}: {
  edge: GraphEdge;
  onClose: () => void;
}) {
  return (
    <aside className="fixed right-4 top-20 z-30 w-80 max-w-[90vw] bg-surface border border-border rounded-xl shadow-2xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-body-md font-bold text-on-surface">关系详情</h3>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded hover:bg-surface-container-low text-on-surface-variant flex items-center justify-center flex-shrink-0"
        >
          <Icon name="close" className="text-[16px]" />
        </button>
      </div>
      <div className="space-y-1.5">
        <DetailRow label="类型" value={edge.label || "RELATED"} />
        <DetailRow label="起点" value={edge.source} mono />
        <DetailRow label="终点" value={edge.target} mono />
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/*  关系管理                                                           */
/* ------------------------------------------------------------------ */
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

/* ------------------------------------------------------------------ */
/*  溯源 / 共指                                                        */
/* ------------------------------------------------------------------ */
function TraceView({ data, type }: { data: TraceResponse; type: "trace" | "coref" }) {
  // 兼容后端返回的多种字段：chain / evidence(溯源) / corefs(共指)
  const pathGroups: { label: string; nodes: string[] }[] = [];
  if (type === "trace") {
    const evidence = (data.evidence || []) as Array<{ chain?: string[]; path?: string[]; nodes?: string[] }>;
    evidence.forEach((e, i) => {
      const nodes = e.chain || e.path || e.nodes || [];
      if (nodes.length) pathGroups.push({ label: `证据链 ${i + 1}`, nodes });
    });
  } else {
    const corefs = (data.corefs || []) as Array<{ cluster?: string[]; nodes?: string[]; path?: string[] }>;
    corefs.forEach((c, i) => {
      const nodes = c.cluster || c.nodes || c.path || [];
      if (nodes.length) pathGroups.push({ label: `共指簇 ${i + 1}`, nodes });
    });
  }
  // 兜底：chain 字段
  if (pathGroups.length === 0 && data.chain) {
    const ch = data.chain as unknown;
    if (Array.isArray(ch) && ch.length) {
      pathGroups.push({ label: type === "trace" ? "溯源链" : "共指链", nodes: ch.map(String) });
    }
  }
  return (
    <div className="space-y-4">
      <section className="bg-surface border border-border rounded-xl p-5">
        <h3 className="text-body-md font-bold text-on-surface mb-3">
          {type === "trace" ? "溯源链" : "共指链"} ({pathGroups.length})
        </h3>
        <div className="space-y-2">
          {pathGroups.map((g, i) => (
            <div key={i} className="bg-surface-container-low rounded-lg p-3">
              <div className="text-label-sm text-on-surface-variant mb-1">{g.label}</div>
              <div className="flex items-center gap-2 flex-wrap">
                {g.nodes.map((nid, j) => (
                  <span key={j} className="inline-flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-primary-fixed text-primary rounded text-label-sm font-mono break-all">
                      {nid}
                    </span>
                    {j < g.nodes.length - 1 && (
                      <Icon name="arrow_forward" className="text-on-surface-variant text-[12px]" />
                    )}
                  </span>
                ))}
              </div>
            </div>
          ))}
          {pathGroups.length === 0 && (
            <p className="text-body-sm text-on-surface-variant">未找到路径</p>
          )}
        </div>
      </section>
    </div>
  );
}
