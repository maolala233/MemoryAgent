"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMandol } from "@/hooks/useMandol";
import type { MandolUnitInfo } from "@/types";

export default function UnitsPage() {
  const { units, listUnits, createUnit, deleteUnit, isLoading } = useMandol();
  const [showCreate, setShowCreate] = useState(false);
  const [newUid, setNewUid] = useState("");
  const [newText, setNewText] = useState("");
  const [newSpace, setNewSpace] = useState("");
  const [selectedUnit, setSelectedUnit] = useState<MandolUnitInfo | null>(null);
  const [searchFilter, setSearchFilter] = useState("");

  useEffect(() => {
    listUnits(100, 0);
  }, [listUnits]);

  const handleCreate = async () => {
    if (!newUid.trim() || !newText.trim()) return;
    const result = await createUnit({
      uid: newUid.trim(),
      text: newText.trim(),
      space_name: newSpace.trim() || undefined,
    });
    if (result) {
      setNewUid("");
      setNewText("");
      setNewSpace("");
      setShowCreate(false);
      await listUnits(100, 0);
    }
  };

  const handleDelete = async (uid: string) => {
    if (!confirm(`确定要删除单元 "${uid}" 吗？`)) return;
    if (await deleteUnit(uid)) {
      await listUnits(100, 0);
      if (selectedUnit?.uid === uid) setSelectedUnit(null);
    }
  };

  const filteredUnits = searchFilter.trim()
    ? units.filter((u) => {
        const q = searchFilter.toLowerCase();
        return (
          u.uid.toLowerCase().includes(q) ||
          (u.text || "").toLowerCase().includes(q)
        );
      })
    : units;

  return (
    <AppShell title="记忆单元" subtitle="记忆单元管理">
      <div className="flex-1 flex h-full overflow-hidden">
        {/* 左侧：单元列表 */}
        <div
          className={`flex flex-col overflow-hidden ${
            selectedUnit ? "hidden md:flex md:flex-1 md:border-r md:border-border" : "flex-1"
          }`}
        >
          {/* 操作栏（固定顶部） */}
          <div className="flex-shrink-0 px-panel-padding py-5 bg-surface-bright border-b border-border space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-body-lg font-bold text-on-surface whitespace-nowrap">
                记忆单元 ({filteredUnits.length}
                {searchFilter && filteredUnits.length !== units.length ? ` / ${units.length}` : ""})
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => listUnits(100, 0)}
                  className="text-label-md text-primary hover:underline flex items-center gap-1 px-2 py-1"
                  title="刷新"
                >
                  <Icon name="refresh" className="text-[16px]" /> 刷新
                </button>
                <button
                  onClick={() => setShowCreate(!showCreate)}
                  className="bg-primary text-on-primary px-3 py-1.5 rounded-lg font-bold text-body-sm hover:bg-opacity-90 transition-all flex items-center gap-1"
                >
                  <Icon name={showCreate ? "close" : "add"} className="text-[16px]" />
                  {showCreate ? "取消" : "添加单元"}
                </button>
              </div>
            </div>

            {/* 搜索过滤 */}
            <div className="relative">
              <Icon
                name="search"
                className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]"
              />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="按 UID 或文本过滤..."
                className="w-full pl-10 pr-3 py-2 rounded-lg border border-border bg-surface text-on-surface focus:outline-none focus:border-primary text-body-sm"
              />
              {searchFilter && (
                <button
                  onClick={() => setSearchFilter("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-on-surface-variant hover:text-on-surface rounded"
                  title="清空"
                >
                  <Icon name="close" className="text-[14px]" />
                </button>
              )}
            </div>

            {/* 创建表单 */}
            {showCreate && (
              <section className="bg-surface border border-border rounded-xl p-4 space-y-2">
                <h4 className="text-body-md font-bold text-on-surface">添加记忆单元</h4>
                <input
                  type="text"
                  value={newUid}
                  onChange={(e) => setNewUid(e.target.value)}
                  placeholder="单元 UID（唯一标识，如 msg_001）"
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary text-body-sm"
                />
                <textarea
                  value={newText}
                  onChange={(e) => setNewText(e.target.value)}
                  placeholder="记忆文本内容"
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary resize-none text-body-sm"
                />
                <input
                  type="text"
                  value={newSpace}
                  onChange={(e) => setNewSpace(e.target.value)}
                  placeholder="空间名称（可选）"
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary text-body-sm"
                />
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={handleCreate}
                    disabled={!newUid.trim() || !newText.trim() || isLoading}
                    className="bg-primary text-on-primary px-3 py-1.5 rounded-lg font-bold text-body-sm hover:bg-opacity-90 disabled:opacity-50"
                  >
                    创建
                  </button>
                </div>
              </section>
            )}
          </div>

          {/* 列表（可滚动） */}
          <div className="flex-1 overflow-y-auto custom-scrollbar px-panel-padding py-4">
            {isLoading && units.length === 0 && <Loading size="md" label="加载中..." />}
            {!isLoading && units.length === 0 && !showCreate && (
              <EmptyState
                icon="memory"
                title="暂无记忆单元"
                description="添加一个记忆单元，或通过文档导入构建记忆。"
              />
            )}
            {units.length > 0 && filteredUnits.length === 0 && (
              <EmptyState
                icon="search_off"
                title="没有匹配的单元"
                description={`没有找到包含 "${searchFilter}" 的单元。`}
              />
            )}
            <div className="space-y-2">
              {filteredUnits.map((u) => {
                const isActive = selectedUnit?.uid === u.uid;
                return (
                  <div
                    key={u.uid}
                    onClick={() => setSelectedUnit(u)}
                    className={[
                      "bg-surface border rounded-lg p-3 transition-colors cursor-pointer",
                      isActive
                        ? "border-primary bg-primary-fixed/30 shadow-sm"
                        : "border-border hover:border-primary/40",
                    ].join(" ")}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Icon
                            name="memory"
                            className={[
                              "text-[18px] flex-shrink-0",
                              isActive ? "text-primary" : "text-primary/70",
                            ].join(" ")}
                          />
                          <span
                            className={[
                              "text-body-md font-medium truncate",
                              isActive ? "text-primary" : "text-on-surface",
                            ].join(" ")}
                            title={u.uid}
                          >
                            {u.uid}
                          </span>
                        </div>
                        <p className="text-body-sm text-on-surface-variant line-clamp-2">
                          {u.text || "(无文本内容)"}
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(u.uid);
                        }}
                        className="text-error hover:bg-error/10 p-1 rounded flex-shrink-0"
                        title="删除"
                      >
                        <Icon name="delete" className="text-[18px]" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* 右侧：单元详情 */}
        {selectedUnit && (
          <aside className="w-full md:w-[28rem] xl:w-[32rem] flex-shrink-0 flex flex-col bg-surface-bright overflow-hidden border-l border-border">
            {/* 详情头部（固定） */}
            <div className="flex-shrink-0 px-5 py-4 border-b border-border flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <Icon name="memory" className="text-primary text-[20px] flex-shrink-0" />
                <h3 className="text-body-lg font-bold text-on-surface truncate" title={selectedUnit.uid}>
                  {selectedUnit.uid}
                </h3>
              </div>
              <button
                onClick={() => setSelectedUnit(null)}
                className="p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded"
                title="关闭详情"
              >
                <Icon name="close" className="text-[18px]" />
              </button>
            </div>

            {/* 详情内容（可滚动） */}
            <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-4 space-y-4">
              {/* 文本内容 */}
              <section>
                <div className="flex items-center gap-1.5 mb-2">
                  <Icon name="description" className="text-on-surface-variant text-[16px]" />
                  <p className="text-label-md font-bold text-on-surface-variant">文本内容</p>
                </div>
                <div className="bg-surface border border-border rounded-lg p-3">
                  <p className="text-body-md text-on-surface whitespace-pre-wrap break-words">
                    {selectedUnit.text || "(无文本内容)"}
                  </p>
                </div>
              </section>

              {/* 原始数据 */}
              {Object.keys(selectedUnit.raw_data || {}).length > 1 && (
                <section>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Icon name="data_object" className="text-on-surface-variant text-[16px]" />
                    <p className="text-label-md font-bold text-on-surface-variant">原始数据</p>
                  </div>
                  <pre className="text-body-sm bg-surface border border-border p-3 rounded-lg overflow-x-auto whitespace-pre-wrap break-all">
                    {JSON.stringify(selectedUnit.raw_data, null, 2)}
                  </pre>
                </section>
              )}

              {/* 元数据 */}
              {Object.keys(selectedUnit.metadata || {}).length > 0 && (
                <section>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Icon name="info" className="text-on-surface-variant text-[16px]" />
                    <p className="text-label-md font-bold text-on-surface-variant">元数据</p>
                  </div>
                  <pre className="text-body-sm bg-surface border border-border p-3 rounded-lg overflow-x-auto whitespace-pre-wrap break-all">
                    {JSON.stringify(selectedUnit.metadata, null, 2)}
                  </pre>
                </section>
              )}
            </div>
          </aside>
        )}
      </div>
    </AppShell>
  );
}
