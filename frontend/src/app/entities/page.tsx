"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMandol } from "@/hooks/useMandol";
import type { MandolUnitInfo } from "@/types";

export default function EntitiesPage() {
  const { units, isLoading, error, listUnits } = useMandol();
  const [query, setQuery] = useState("");
  const [selectedUnit, setSelectedUnit] = useState<MandolUnitInfo | null>(null);

  useEffect(() => {
    listUnits(500);
  }, [listUnits]);

  // 过滤出实体类型的单元
  const entities = units.filter(
    (u) => u.metadata?.type === "entity" || u.raw_data?.entity_name || u.metadata?.category === "entity_relation"
  );

  const filtered = query
    ? entities.filter(
        (e) =>
          (e.raw_data?.entity_name || e.uid).toLowerCase().includes(query.toLowerCase()) ||
          (e.text || "").toLowerCase().includes(query.toLowerCase()),
      )
    : entities;

  return (
    <AppShell title="知识实体" subtitle="浏览从记忆中提取的实体">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8">
          {/* 搜索栏 */}
          <div className="mb-6">
            <form onSubmit={(e) => e.preventDefault()} className="relative">
              <Icon name="search" className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant text-[20px]" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索实体..."
                className="w-full pl-12 pr-4 py-3 bg-surface border border-border rounded-xl focus:ring-2 focus:ring-primary outline-none text-body-md"
              />
            </form>
          </div>

          {error && (
            <div className="bg-error/10 border border-error/20 text-error rounded-lg p-4 mb-6 flex items-center gap-2">
              <Icon name="error" filled />
              <span className="text-body-md">{error}</span>
            </div>
          )}

          {isLoading && <Loading label="加载实体中..." />}

          {!isLoading && filtered.length === 0 && !error && (
            <EmptyState
              icon="neurology"
              title="未找到实体"
              description="请先上传文档到记忆库并执行记忆构建，系统将自动提取实体。"
              action={
                <Link href="/build" className="text-primary hover:underline">
                  前往记忆构建
                </Link>
              }
            />
          )}

          {/* 实体网格 */}
          {!isLoading && filtered.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((entity) => {
                const name = entity.raw_data?.entity_name || entity.uid;
                const type = entity.metadata?.entity_type || entity.raw_data?.entity_type || "实体";
                const aliases: string[] = entity.raw_data?.aliases || [];
                return (
                  <div
                    key={entity.uid}
                    onClick={() => setSelectedUnit(entity)}
                    className="bg-surface border border-border rounded-xl p-5 hover:border-primary transition-all cursor-pointer"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Icon name="person" className="text-primary text-[24px]" />
                        <h3 className="text-body-lg font-bold text-on-surface">{name}</h3>
                      </div>
                      <Pill variant="info" size="sm">{type}</Pill>
                    </div>
                    <p className="text-body-sm text-on-surface-variant line-clamp-3 mb-3">
                      {entity.text}
                    </p>
                    {aliases.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {aliases.slice(0, 3).map((alias, i) => (
                          <Pill key={i} size="sm" variant="default">{alias}</Pill>
                        ))}
                        {aliases.length > 3 && (
                          <span className="text-label-sm text-outline">+{aliases.length - 3} 更多</span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* 实体详情弹窗 */}
          {selectedUnit && (
            <div
              className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
              onClick={() => setSelectedUnit(null)}
            >
              <div
                className="bg-surface border border-border rounded-xl p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <Icon name="person" className="text-primary text-[32px]" />
                    <div>
                      <h2 className="text-headline-md font-bold text-on-surface">
                        {selectedUnit.raw_data?.entity_name || selectedUnit.uid}
                      </h2>
                      <Pill variant="info" size="sm">
                        {selectedUnit.metadata?.entity_type || selectedUnit.raw_data?.entity_type || "实体"}
                      </Pill>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedUnit(null)}
                    className="p-2 hover:bg-surface-container-low rounded-lg transition-colors"
                  >
                    <Icon name="close" className="text-[20px]" />
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <h3 className="text-body-md font-bold text-on-surface mb-2">描述</h3>
                    <p className="text-body-md text-on-surface-variant">{selectedUnit.text}</p>
                  </div>

                  {selectedUnit.raw_data?.aliases && selectedUnit.raw_data.aliases.length > 0 && (
                    <div>
                      <h3 className="text-body-md font-bold text-on-surface mb-2">别名</h3>
                      <div className="flex flex-wrap gap-2">
                        {selectedUnit.raw_data.aliases.map((alias: string, i: number) => (
                          <Pill key={i} size="sm">{alias}</Pill>
                        ))}
                      </div>
                    </div>
                  )}

                  <div>
                    <h3 className="text-body-md font-bold text-on-surface mb-2">元数据</h3>
                    <pre className="text-label-md font-mono text-on-surface-variant bg-surface-container-low p-3 rounded overflow-x-auto">
                      {JSON.stringify(selectedUnit.metadata, null, 2)}
                    </pre>
                  </div>

                  <div className="flex gap-2">
                    <Link
                      href={`/graph?q=${encodeURIComponent(selectedUnit.raw_data?.entity_name || selectedUnit.uid)}`}
                      className="flex-1 bg-primary text-on-primary py-2 rounded-lg font-bold text-body-md hover:opacity-90 transition-all flex items-center justify-center gap-2"
                    >
                      <Icon name="account_tree" className="text-[18px]" />
                      查看图谱
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
