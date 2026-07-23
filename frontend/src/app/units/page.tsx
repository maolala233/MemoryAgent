"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { EmptyState } from "@/components/shared/EmptyState";
import { Pagination } from "@/components/shared/Pagination";
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
  // 分页状态
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listUnits(pageSize, (page - 1) * pageSize).then((data) => {
      if (cancelled || !data) return;
      setTotal(data.total);
      // 若当前页越界（例如删了最后一页的最后一条），自动回退
      const lastPage = Math.max(1, Math.ceil(data.total / pageSize));
      if (page > lastPage) setPage(lastPage);
    });
    return () => {
      cancelled = true;
    };
  }, [listUnits, page, pageSize]);

  const refetch = () =>
    listUnits(pageSize, (page - 1) * pageSize).then((data) => {
      if (data) setTotal(data.total);
    });

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
      // 新建后回到第一页, 避免漏看
      setPage(1);
      await refetch();
    }
  };

  const handleDelete = async (uid: string) => {
    if (!confirm(`确定要删除单元 "${uid}" 吗？`)) return;
    if (await deleteUnit(uid)) {
      await refetch();
      if (selectedUnit?.uid === uid) setSelectedUnit(null);
    }
  };

  // 搜索是纯前端过滤, 仅影响当前页 items
  const filteredUnits = searchFilter.trim()
    ? units.filter((u) => {
        const q = searchFilter.toLowerCase();
        return (
          u.uid.toLowerCase().includes(q) ||
          (u.text || "").toLowerCase().includes(q)
        );
      })
    : units;

  // 关闭详情时支持 ESC
  useEffect(() => {
    if (!selectedUnit) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedUnit(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedUnit]);

  return (
    <AppShell title="记忆单元" subtitle={`${total} 个`}>
      {/* 整页滚动, 与 memory 页面一致, 让分页器始终在内容流底部可滚动到 */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-body-lg font-bold text-on-surface whitespace-nowrap">
              记忆单元
              {searchFilter && filteredUnits.length !== units.length ? (
                <span className="text-on-surface-variant font-normal">
                  {" "}
                  (过滤后 {filteredUnits.length})
                </span>
              ) : null}
            </h3>
            <div className="relative flex-1 min-w-[240px]">
              <Icon
                name="search"
                className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]"
              />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="按 UID 或文本过滤..."
                className="w-full pl-10 pr-9 py-2 rounded-lg border border-border bg-surface text-on-surface focus:outline-none focus:border-primary text-body-sm"
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
            <button
              onClick={refetch}
              className="text-label-md text-primary hover:underline flex items-center gap-1 px-2 py-1"
              title="刷新"
            >
              <Icon name="refresh" className="text-[16px]" /> 刷新
            </button>
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="bg-primary text-on-primary px-3 py-2 rounded-lg font-bold text-body-sm hover:bg-opacity-90 transition-all flex items-center gap-1"
            >
              <Icon name={showCreate ? "close" : "add"} className="text-[16px]" />
              {showCreate ? "取消" : "添加单元"}
            </button>
          </div>

          {/* 创建表单 */}
          {showCreate && (
            <section className="bg-surface-bright border border-border rounded-xl p-5 space-y-3">
              <h4 className="text-body-md font-bold text-on-surface">添加记忆单元</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <input
                  type="text"
                  value={newUid}
                  onChange={(e) => setNewUid(e.target.value)}
                  placeholder="单元 UID（唯一标识，如 msg_001）"
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-on-surface focus:outline-none focus:border-primary text-body-sm"
                />
                <input
                  type="text"
                  value={newSpace}
                  onChange={(e) => setNewSpace(e.target.value)}
                  placeholder="空间名称（可选）"
                  className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-on-surface focus:outline-none focus:border-primary text-body-sm"
                />
              </div>
              <textarea
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                placeholder="记忆文本内容"
                rows={3}
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-on-surface focus:outline-none focus:border-primary resize-none text-body-sm"
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCreate}
                  disabled={!newUid.trim() || !newText.trim() || isLoading}
                  className="bg-primary text-on-primary px-4 py-1.5 rounded-lg font-bold text-body-sm hover:bg-opacity-90 disabled:opacity-50"
                >
                  创建
                </button>
                <span className="text-label-sm text-on-surface-variant">
                  提示: UID 需唯一, 文本会作为该记忆的内容入库。
                </span>
              </div>
            </section>
          )}

          {/* 列表 */}
          <div className="space-y-2">
            {isLoading && units.length === 0 && (
              <div className="flex justify-center py-8">
                <Loading size="md" label="加载中..." />
              </div>
            )}
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
            {filteredUnits.map((u) => {
              const isActive = selectedUnit?.uid === u.uid;
              return (
                <div
                  key={u.uid}
                  onClick={() => setSelectedUnit(u)}
                  className={[
                    "bg-surface border rounded-lg p-4 transition-colors cursor-pointer",
                    isActive
                      ? "border-primary bg-primary-fixed/30 shadow-sm"
                      : "border-border hover:border-primary/40",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
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
                      className="text-error hover:bg-error/10 p-1.5 rounded flex-shrink-0"
                      title="删除"
                    >
                      <Icon name="delete" className="text-[18px]" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* 分页（固定在内容流底部, 滚动到底即可见） */}
          <div className="bg-surface-bright rounded-lg border border-border px-4 py-3">
            <Pagination
              page={page}
              pageSize={pageSize}
              total={total}
              onPageChange={setPage}
              onPageSizeChange={(n) => {
                setPageSize(n);
                setPage(1);
              }}
            />
          </div>
        </div>
      </div>

      {/* 单元详情：slide-over 抽屉 (覆盖在内容之上, 不再与列表挤布局) */}
      {selectedUnit && (
        <div className="fixed inset-0 z-50 flex">
          {/* 背景遮罩 */}
          <div
            className="flex-1 bg-black/40 backdrop-blur-sm"
            onClick={() => setSelectedUnit(null)}
          />
          {/* 抽屉本体 */}
          <aside className="w-full max-w-[32rem] bg-surface-bright flex flex-col shadow-2xl">
            {/* 抽屉头部 */}
            <div className="flex-shrink-0 px-5 py-4 border-b border-border flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <Icon name="memory" className="text-primary text-[20px] flex-shrink-0" />
                <h3
                  className="text-body-lg font-bold text-on-surface truncate"
                  title={selectedUnit.uid}
                >
                  {selectedUnit.uid}
                </h3>
              </div>
              <button
                onClick={() => setSelectedUnit(null)}
                className="p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded"
                title="关闭详情"
                aria-label="关闭详情"
              >
                <Icon name="close" className="text-[18px]" />
              </button>
            </div>

            {/* 抽屉内容（可滚动） */}
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
        </div>
      )}
    </AppShell>
  );
}
