"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMandol } from "@/hooks/useMandol";
import type { SpaceInfo } from "@/types";

export default function SpacesPage() {
  const { spaces, listSpaces, createSpace, deleteSpace, isLoading } = useMandol();
  const [newName, setNewName] = useState("");
  const [selectedSpace, setSelectedSpace] = useState<SpaceInfo | null>(null);

  useEffect(() => {
    listSpaces();
  }, [listSpaces]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    const result = await createSpace(newName.trim());
    if (result) {
      setNewName("");
      await listSpaces();
    }
  };

  const handleDelete = async (name: string, cascade: boolean) => {
    if (!confirm(`确定要删除空间 "${name}" 吗？${cascade ? "（级联删除所有单元）" : ""}`)) return;
    if (await deleteSpace(name, cascade)) {
      await listSpaces();
      if (selectedSpace?.name === name) setSelectedSpace(null);
    }
  };

  return (
    <AppShell title="记忆空间" subtitle="空间管理与层级结构">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">
          {/* 创建空间 */}
          <section className="bg-surface border border-border rounded-xl p-5">
            <h3 className="text-body-lg font-bold text-on-surface mb-4">创建记忆空间</h3>
            <div className="flex items-center gap-3">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="输入空间名称，如：客服-用户A"
                className="flex-1 px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              />
              <button
                onClick={handleCreate}
                disabled={!newName.trim() || isLoading}
                className="bg-primary text-on-primary px-5 py-2 rounded-lg font-bold text-body-md hover:bg-opacity-90 transition-all disabled:opacity-50"
              >
                创建
              </button>
            </div>
          </section>

          {/* 空间列表 */}
          <section className="bg-surface border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-body-lg font-bold text-on-surface">
                空间列表 ({spaces.length})
              </h3>
              <button
                onClick={() => listSpaces()}
                className="text-label-md text-primary hover:underline flex items-center gap-1"
              >
                <Icon name="refresh" className="text-[14px]" /> 刷新
              </button>
            </div>
            {isLoading && spaces.length === 0 && <Loading size="md" label="加载中..." />}
            {!isLoading && spaces.length === 0 && (
              <EmptyState
                icon="workspaces"
                title="暂无空间"
                description="创建一个记忆空间来组织你的记忆单元。"
              />
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {spaces.map((sp) => (
                <div
                  key={sp.name}
                  className="border border-border rounded-lg p-4 hover:border-primary/40 transition-colors cursor-pointer"
                  onClick={() => setSelectedSpace(sp)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <Icon name="workspaces" className="text-primary text-[24px]" />
                    <span className="text-label-sm text-on-surface-variant">
                      {sp.unit_count} 个单元
                    </span>
                  </div>
                  <p className="text-body-md font-medium text-on-surface truncate">{sp.name}</p>
                  {sp.child_spaces.length > 0 && (
                    <p className="text-label-sm text-on-surface-variant mt-1">
                      子空间: {sp.child_spaces.length}
                    </p>
                  )}
                  {sp.summary && (
                    <p className="text-body-sm text-on-surface-variant mt-2 line-clamp-2">
                      {sp.summary}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(sp.name, false);
                      }}
                      className="text-label-sm text-error hover:underline"
                    >
                      删除
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(sp.name, true);
                      }}
                      className="text-label-sm text-error hover:underline"
                    >
                      级联删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* 空间详情 */}
          {selectedSpace && (
            <section className="bg-surface border border-border rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-body-lg font-bold text-on-surface">
                  空间详情: {selectedSpace.name}
                </h3>
                <button
                  onClick={() => setSelectedSpace(null)}
                  className="text-label-md text-on-surface-variant hover:text-on-surface"
                >
                  关闭
                </button>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-body-sm text-on-surface-variant w-24">单元数:</span>
                  <span className="text-body-md text-on-surface">{selectedSpace.unit_count}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-body-sm text-on-surface-variant w-24">子空间:</span>
                  <div className="flex flex-wrap gap-1">
                    {selectedSpace.child_spaces.length > 0 ? (
                      selectedSpace.child_spaces.map((c) => (
                        <span key={c} className="px-2 py-0.5 bg-primary-fixed text-primary rounded text-label-sm">
                          {c}
                        </span>
                      ))
                    ) : (
                      <span className="text-body-sm text-on-surface-variant">无</span>
                    )}
                  </div>
                </div>
                {selectedSpace.summary && (
                  <div className="flex items-start gap-2">
                    <span className="text-body-sm text-on-surface-variant w-24 mt-1">摘要:</span>
                    <span className="text-body-md text-on-surface flex-1">{selectedSpace.summary}</span>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      </div>
    </AppShell>
  );
}
