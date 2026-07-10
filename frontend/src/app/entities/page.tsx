"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMandol } from "@/hooks/useMandol";
import type { MandolUnitInfo } from "@/types";

export default function EntitiesPage() {
  const { listEntities, deleteUnit, isLoading, error } = useMandol();
  const [items, setItems] = useState<MandolUnitInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<MandolUnitInfo | null>(null);

  const load = async () => {
    setLoading(true);
    const data = await listEntities(500);
    if (data) {
      setItems(data.items || []);
      setTotal(data.total || 0);
    }
    setLoading(false);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDelete = async (uid: string) => {
    if (!confirm(`确定要删除实体 "${uid}" 吗？`)) return;
    if (await deleteUnit(uid)) {
      await load();
      if (selected?.uid === uid) setSelected(null);
    }
  };

  const filtered = search.trim()
    ? items.filter((u) => {
        const q = search.toLowerCase();
        return (
          u.uid.toLowerCase().includes(q) ||
          (u.text || "").toLowerCase().includes(q) ||
          (u.space_name || "").toLowerCase().includes(q)
        );
      })
    : items;

  return (
    <AppShell title="实体" subtitle="已抽取的实体（来自 knowledge_entity 空间）">
      <div className="flex-1 flex h-full overflow-hidden">
        {/* 左侧：实体列表 */}
        <div
          className={`flex flex-col overflow-hidden ${
            selected ? "hidden md:flex md:flex-1 md:border-r md:border-border" : "flex-1"
          }`}
        >
          {/* 顶部操作栏 */}
          <div className="flex-shrink-0 px-panel-padding py-5 bg-surface-bright border-b border-border space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-body-lg font-bold text-on-surface whitespace-nowrap">
                实体列表 ({filtered.length}
                {search && filtered.length !== items.length ? ` / ${items.length}` : ""})
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={load}
                  className="text-label-md text-primary hover:underline flex items-center gap-1 px-2 py-1"
                  title="刷新"
                >
                  <Icon name="refresh" className="text-[16px]" /> 刷新
                </button>
                <a
                  href="/build"
                  className="bg-primary text-on-primary px-3 py-1.5 rounded-lg font-bold text-body-sm hover:bg-opacity-90 transition-all flex items-center gap-1"
                >
                  <Icon name="auto_awesome" className="text-[16px]" /> 构建
                </a>
              </div>
            </div>

            {/* 搜索 */}
            <div className="relative">
              <Icon
                name="search"
                className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]"
              />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="按 UID / 文本 / 空间名过滤..."
                className="w-full pl-10 pr-3 py-2 rounded-lg border border-border bg-surface text-on-surface focus:outline-none focus:border-primary text-body-sm"
              />
              {search && (
                <button
                  onClick={() => setSearch("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-on-surface-variant hover:text-on-surface rounded"
                  title="清空"
                >
                  <Icon name="close" className="text-[14px]" />
                </button>
              )}
            </div>

            <p className="text-body-sm text-on-surface-variant">
              总计 <span className="font-bold text-primary">{total}</span> 个实体
            </p>
          </div>

          {/* 列表 */}
          <div className="flex-1 overflow-y-auto custom-scrollbar px-panel-padding py-4">
            {loading && items.length === 0 && <Loading size="md" label="加载中..." />}
            {!loading && items.length === 0 && (
              <EmptyState
                icon="person_off"
                title="暂无实体"
                description="尚未抽取任何实体。前往「高阶记忆构建」运行一次实体抽取。"
              />
            )}
            {items.length > 0 && filtered.length === 0 && (
              <EmptyState
                icon="search_off"
                title="没有匹配的实体"
                description={`没有找到包含 "${search}" 的实体。`}
              />
            )}
            <div className="space-y-2">
              {filtered.map((u) => {
                const isActive = selected?.uid === u.uid;
                return (
                  <div
                    key={u.uid}
                    onClick={() => setSelected(u)}
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
                            name="person"
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
                          {u.space_name && (
                            <span className="text-label-sm px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant">
                              {u.space_name}
                            </span>
                          )}
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

        {/* 右侧：详情 */}
        {selected && (
          <aside className="w-full md:w-[28rem] xl:w-[32rem] flex-shrink-0 flex flex-col bg-surface-bright overflow-hidden border-l border-border">
            <div className="flex-shrink-0 px-5 py-4 border-b border-border flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <Icon name="person" className="text-primary text-[20px] flex-shrink-0" />
                <h3 className="text-body-lg font-bold text-on-surface truncate" title={selected.uid}>
                  {selected.uid}
                </h3>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded"
                title="关闭详情"
              >
                <Icon name="close" className="text-[18px]" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-4 space-y-4">
              <section>
                <div className="flex items-center gap-1.5 mb-2">
                  <Icon name="description" className="text-on-surface-variant text-[16px]" />
                  <p className="text-label-md font-bold text-on-surface-variant">实体描述</p>
                </div>
                <div className="bg-surface border border-border rounded-lg p-3">
                  <p className="text-body-md text-on-surface whitespace-pre-wrap break-words">
                    {selected.text || "(无文本内容)"}
                  </p>
                </div>
              </section>

              {selected.space_name && (
                <section>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Icon name="workspaces" className="text-on-surface-variant text-[16px]" />
                    <p className="text-label-md font-bold text-on-surface-variant">所属空间</p>
                  </div>
                  <div className="bg-surface border border-border rounded-lg p-3 text-body-md text-on-surface">
                    {selected.space_name}
                  </div>
                </section>
              )}

              {Object.keys(selected.metadata || {}).length > 0 && (
                <section>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Icon name="info" className="text-on-surface-variant text-[16px]" />
                    <p className="text-label-md font-bold text-on-surface-variant">元数据</p>
                  </div>
                  <pre className="text-body-sm bg-surface border border-border p-3 rounded-lg overflow-x-auto whitespace-pre-wrap break-all">
                    {JSON.stringify(selected.metadata, null, 2)}
                  </pre>
                </section>
              )}

              {Object.keys(selected.raw_data || {}).length > 0 && (
                <section>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Icon name="data_object" className="text-on-surface-variant text-[16px]" />
                    <p className="text-label-md font-bold text-on-surface-variant">原始数据</p>
                  </div>
                  <pre className="text-body-sm bg-surface border border-border p-3 rounded-lg overflow-x-auto whitespace-pre-wrap break-all">
                    {JSON.stringify(selected.raw_data, null, 2)}
                  </pre>
                </section>
              )}
            </div>
          </aside>
        )}
      </div>

      {error && (
        <div className="px-panel-padding py-2 text-body-sm text-error bg-error/10 border-t border-error/30">
          {error}
        </div>
      )}
    </AppShell>
  );
}
