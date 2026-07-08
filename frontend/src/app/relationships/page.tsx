"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMandol } from "@/hooks/useMandol";
import { api, ApiError } from "@/services/api";
import type { RelationshipInfo } from "@/types";

const REL_TYPES = [
  "PRECEDES", "FOLLOWS", "SEMANTIC_SIMILAR", "RELATED_TO",
  "COREF", "CAUSES", "CAUSED_BY", "INVOLVES",
  "EVIDENCED_BY", "ALIAS_OF",
];

const REL_LABELS: Record<string, string> = {
  PRECEDES: "时序前驱",
  FOLLOWS: "时序后继",
  SEMANTIC_SIMILAR: "语义相似",
  RELATED_TO: "通用关系",
  COREF: "共指关系",
  CAUSES: "导致",
  CAUSED_BY: "被导致",
  INVOLVES: "参与",
  EVIDENCED_BY: "溯源",
  ALIAS_OF: "别名",
};

export default function RelationshipsPage() {
  const { relationships, listRelationships, createRelationship, isLoading } = useMandol();
  const [queryUid, setQueryUid] = useState("");
  const [direction, setDirection] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [relType, setRelType] = useState(REL_TYPES[3]);
  const [graphRelations, setGraphRelations] = useState<any[]>([]);

  const handleSearch = async () => {
    if (!queryUid.trim()) return;
    await listRelationships(queryUid.trim(), direction);
  };

  const handleCreate = async () => {
    if (!source.trim() || !target.trim()) return;
    if (await createRelationship(source.trim(), target.trim(), relType)) {
      setSource("");
      setTarget("");
      setShowCreate(false);
      if (queryUid.trim()) {
        await listRelationships(queryUid.trim(), direction);
      }
    }
  };

  const handleDelete = async (src: string, tgt: string, rt: string) => {
    if (!confirm(`确定要删除关系 ${src} --[${rt}]--> ${tgt} 吗？`)) return;
    try {
      await api.del("mandol/relationships", { source: src, target: tgt, rel_type: rt });
      if (queryUid.trim()) {
        await listRelationships(queryUid.trim(), direction);
      }
    } catch (err) {
      alert(`删除失败: ${err instanceof ApiError ? err.detail : "未知错误"}`);
    }
  };

  const handleSearchGraph = async () => {
    try {
      const data = await api.get<any[]>("mandol/graph/relations?limit=100");
      setGraphRelations(data);
    } catch {
      setGraphRelations([]);
    }
  };

  useEffect(() => {
    handleSearchGraph();
  }, []);

  return (
    <AppShell title="关系管理" subtitle="记忆单元关系管理">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">
          {/* 关系类型说明 */}
          <section className="bg-surface border border-border rounded-xl p-5">
            <h3 className="text-body-lg font-bold text-on-surface mb-3">支持的关系类型</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
              {REL_TYPES.map((rt) => (
                <div key={rt} className="bg-surface-container-low rounded-lg p-2">
                  <p className="text-body-sm font-medium text-on-surface">{rt}</p>
                  <p className="text-label-sm text-on-surface-variant">{REL_LABELS[rt]}</p>
                </div>
              ))}
            </div>
          </section>

          {/* 创建关系 */}
          <section className="bg-surface border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-body-lg font-bold text-on-surface">添加关系</h3>
              <button
                onClick={() => setShowCreate(!showCreate)}
                className="text-label-md text-primary hover:underline"
              >
                {showCreate ? "收起" : "展开"}
              </button>
            </div>
            {showCreate && (
              <div className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <input
                    type="text"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    placeholder="源单元 UID"
                    className="px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
                  />
                  <select
                    value={relType}
                    onChange={(e) => setRelType(e.target.value)}
                    className="px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
                  >
                    {REL_TYPES.map((rt) => (
                      <option key={rt} value={rt}>{rt} ({REL_LABELS[rt]})</option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={target}
                    onChange={(e) => setTarget(e.target.value)}
                    placeholder="目标单元 UID"
                    className="px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
                  />
                </div>
                <button
                  onClick={handleCreate}
                  disabled={!source.trim() || !target.trim() || isLoading}
                  className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:bg-opacity-90 disabled:opacity-50"
                >
                  创建关系
                </button>
              </div>
            )}
          </section>

          {/* 查询单元关系 */}
          <section className="bg-surface border border-border rounded-xl p-5">
            <h3 className="text-body-lg font-bold text-on-surface mb-4">查询单元关系</h3>
            <div className="flex items-center gap-3 mb-4">
              <input
                type="text"
                value={queryUid}
                onChange={(e) => setQueryUid(e.target.value)}
                placeholder="输入单元 UID"
                className="flex-1 px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value)}
                className="px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
              >
                <option value="all">全部</option>
                <option value="out">出边</option>
                <option value="in">入边</option>
              </select>
              <button
                onClick={handleSearch}
                disabled={!queryUid.trim() || isLoading}
                className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:bg-opacity-90 disabled:opacity-50"
              >
                查询
              </button>
            </div>
            {isLoading && relationships.length === 0 && <Loading size="md" label="查询中..." />}
            {!isLoading && queryUid && relationships.length === 0 && (
              <p className="text-body-sm text-on-surface-variant">未找到关系。</p>
            )}
            <div className="space-y-2">
              {relationships.map((rel, i) => (
                <div key={i} className="bg-surface-container-low rounded-lg p-3 flex items-center gap-3">
                  <span className="text-body-sm text-on-surface font-medium truncate flex-1">{rel.source}</span>
                  <span className="px-2 py-0.5 bg-primary-fixed text-primary rounded text-label-sm whitespace-nowrap">
                    {rel.rel_type}
                  </span>
                  <Icon name="arrow_forward" className="text-on-surface-variant text-[16px]" />
                  <span className="text-body-sm text-on-surface font-medium truncate flex-1">{rel.target}</span>
                  <button
                    onClick={() => handleDelete(rel.source, rel.target, rel.rel_type)}
                    className="text-error hover:bg-error/10 p-1 rounded"
                  >
                    <Icon name="delete" className="text-[16px]" />
                  </button>
                </div>
              ))}
            </div>
          </section>

          {/* 全图关系概览 */}
          <section className="bg-surface border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-body-lg font-bold text-on-surface">全图关系概览 ({graphRelations.length})</h3>
              <button
                onClick={handleSearchGraph}
                className="text-label-md text-primary hover:underline flex items-center gap-1"
              >
                <Icon name="refresh" className="text-[14px]" /> 刷新
              </button>
            </div>
            {graphRelations.length === 0 ? (
              <EmptyState icon="link" title="暂无关系" description="构建高阶记忆后会自动生成关系。" />
            ) : (
              <div className="space-y-1 max-h-96 overflow-y-auto custom-scrollbar">
                {graphRelations.slice(0, 100).map((rel, i) => (
                  <div key={i} className="text-body-sm text-on-surface-variant py-1 border-b border-border/50">
                    <span className="text-on-surface">{rel.source}</span>
                    {" →["}
                    <span className="text-primary">{rel.properties?.rel_type || "RELATED"}</span>
                    {"]→ "}
                    <span className="text-on-surface">{rel.target}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </AppShell>
  );
}
