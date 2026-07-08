"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { EmptyState } from "@/components/shared/EmptyState";
import { Pill } from "@/components/shared/Pill";
import { useMandol } from "@/hooks/useMandol";
import type { SpaceInfo, MandolUnitInfo } from "@/types";

export default function SpacesPage() {
  const {
    spaces,
    listSpaces,
    createSpace,
    deleteSpace,
    listUnitsInSpace,
    addUnitToSpace,
    removeUnitFromSpace,
    isLoading,
  } = useMandol();
  const [newName, setNewName] = useState("");
  const [selectedSpace, setSelectedSpace] = useState<SpaceInfo | null>(null);
  const [unitsInSpace, setUnitsInSpace] = useState<MandolUnitInfo[]>([]);
  const [unitsLoading, setUnitsLoading] = useState(false);
  const [showAddUnit, setShowAddUnit] = useState(false);
  const [newUnitUid, setNewUnitUid] = useState("");
  const [newUnitText, setNewUnitText] = useState("");
  const [searchFilter, setSearchFilter] = useState("");
  const [operationLog, setOperationLog] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    listSpaces();
  }, [listSpaces]);

  // 选中空间后加载其单元
  useEffect(() => {
    if (!selectedSpace) {
      setUnitsInSpace([]);
      return;
    }
    setUnitsLoading(true);
    listUnitsInSpace(selectedSpace.name, 200)
      .then((data) => setUnitsInSpace(data?.items || []))
      .finally(() => setUnitsLoading(false));
  }, [selectedSpace, listUnitsInSpace]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    const result = await createSpace(newName.trim());
    if (result) {
      setNewName("");
      setOperationLog({ kind: "ok", text: `已创建空间「${result.name}」` });
      await listSpaces();
    }
  };

  const handleDelete = async (name: string, cascade: boolean) => {
    const msg = cascade
      ? `确定要级联删除空间「${name}」吗？\n\n将同时删除该空间（含子空间）下的所有记忆单元，此操作不可恢复。`
      : `确定要删除空间「${name}」吗？\n\n仅在该空间为空（无单元、无子空间）时可成功删除。`;
    if (!confirm(msg)) return;
    const ok = await deleteSpace(name, cascade);
    if (ok) {
      setOperationLog({
        kind: "ok",
        text: cascade
          ? `已级联删除空间「${name}」及其所有单元`
          : `已删除空间「${name}」`,
      });
      await listSpaces();
      if (selectedSpace?.name === name) setSelectedSpace(null);
    } else {
      setOperationLog({ kind: "err", text: `删除空间「${name}」失败，请检查后端日志` });
    }
  };

  const handleAddUnit = async () => {
    if (!selectedSpace || !newUnitUid.trim() || !newUnitText.trim()) return;
    // 先创建单元（带 space_name），再显式加入空间
    try {
      const resp = await fetch("/api/mandol/units", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          uid: newUnitUid.trim(),
          text: newUnitText.trim(),
          space_name: selectedSpace.name,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        setOperationLog({ kind: "err", text: `创建单元失败：${err.detail || resp.statusText}` });
        return;
      }
      const ok = await addUnitToSpace(newUnitUid.trim(), selectedSpace.name);
      if (ok) {
        setOperationLog({ kind: "ok", text: `已添加单元「${newUnitUid}」到空间` });
        setNewUnitUid("");
        setNewUnitText("");
        setShowAddUnit(false);
        // 刷新单元列表与空间信息
        const data = await listUnitsInSpace(selectedSpace.name, 200);
        setUnitsInSpace(data?.items || []);
        await listSpaces();
        // 更新 selectedSpace 计数
        setSelectedSpace((prev) =>
          prev ? { ...prev, unit_count: prev.unit_count + 1 } : prev
        );
      }
    } catch (e) {
      setOperationLog({ kind: "err", text: `添加失败：${(e as Error).message}` });
    }
  };

  const handleRemoveUnit = async (uid: string) => {
    if (!selectedSpace) return;
    if (!confirm(`确定要从空间「${selectedSpace.name}」中移除单元「${uid}」吗？\n（单元本身不会被删除）`)) return;
    const ok = await removeUnitFromSpace(uid, selectedSpace.name);
    if (ok) {
      setOperationLog({ kind: "ok", text: `已从空间移除单元「${uid}」` });
      setUnitsInSpace((arr) => arr.filter((u) => u.uid !== uid));
      setSelectedSpace((prev) =>
        prev ? { ...prev, unit_count: Math.max(0, prev.unit_count - 1) } : prev
      );
    } else {
      setOperationLog({ kind: "err", text: `移除单元失败` });
    }
  };

  const filteredSpaces = searchFilter.trim()
    ? spaces.filter((s) => s.name.toLowerCase().includes(searchFilter.toLowerCase()))
    : spaces;

  // 5 秒后自动清空操作日志
  useEffect(() => {
    if (!operationLog) return;
    const t = setTimeout(() => setOperationLog(null), 5000);
    return () => clearTimeout(t);
  }, [operationLog]);

  return (
    <AppShell title="记忆空间" subtitle="空间管理与层级结构">
      <div className="flex-1 flex h-full overflow-hidden">
        {/* 左侧：空间列表 */}
        <div
          className={`flex flex-col overflow-hidden ${
            selectedSpace ? "hidden md:flex md:flex-1 md:border-r md:border-border" : "flex-1"
          }`}
        >
          {/* 顶部固定区：功能说明 + 创建 + 搜索 */}
          <div className="flex-shrink-0 px-panel-padding py-5 bg-surface-bright border-b border-border space-y-4">
            {/* 功能说明 */}
            <div className="bg-primary-fixed/40 border border-primary/20 rounded-lg p-3 flex items-start gap-2">
              <Icon name="info" className="text-primary text-[20px] flex-shrink-0 mt-0.5" />
              <div className="text-label-md text-on-surface">
                <p className="font-bold text-primary mb-1">什么是记忆空间？</p>
                <p className="text-on-surface-variant leading-relaxed">
                  记忆空间是记忆单元的<strong>逻辑分组容器</strong>，支持层级嵌套。
                  可用于按用户、会话、主题或业务线隔离记忆，并在检索时限定范围。
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between gap-3">
              <h3 className="text-body-lg font-bold text-on-surface whitespace-nowrap">
                空间 ({filteredSpaces.length}
                {searchFilter && filteredSpaces.length !== spaces.length ? ` / ${spaces.length}` : ""})
              </h3>
              <button
                onClick={() => listSpaces()}
                className="text-label-md text-primary hover:underline flex items-center gap-1 px-2 py-1"
                title="刷新"
              >
                <Icon name="refresh" className="text-[16px]" /> 刷新
              </button>
            </div>

            {/* 创建表单 */}
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="输入空间名称，如：客服-用户A / 2026Q1-风控"
                className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface text-on-surface focus:outline-none focus:border-primary text-body-sm"
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              />
              <button
                onClick={handleCreate}
                disabled={!newName.trim() || isLoading}
                className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:bg-opacity-90 transition-all disabled:opacity-50"
              >
                <Icon name="add" className="text-[16px] inline -mt-0.5 mr-1" />
                创建
              </button>
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
                placeholder="按空间名过滤..."
                className="w-full pl-10 pr-3 py-2 rounded-lg border border-border bg-surface text-on-surface focus:outline-none focus:border-primary text-body-sm"
              />
            </div>

            {/* 操作日志提示 */}
            {operationLog && (
              <div
                className={[
                  "px-3 py-2 rounded-lg text-label-sm flex items-center gap-2 animate-in fade-in",
                  operationLog.kind === "ok"
                    ? "bg-success-container text-on-success-container"
                    : "bg-error-container text-on-error-container",
                ].join(" ")}
              >
                <Icon
                  name={operationLog.kind === "ok" ? "check_circle" : "error"}
                  className="text-[16px]"
                />
                {operationLog.text}
              </div>
            )}
          </div>

          {/* 空间列表（可滚动） */}
          <div className="flex-1 overflow-y-auto custom-scrollbar px-panel-padding py-4">
            {isLoading && spaces.length === 0 && <Loading size="md" label="加载中..." />}
            {!isLoading && spaces.length === 0 && (
              <EmptyState
                icon="workspaces"
                title="暂无空间"
                description="创建一个记忆空间来组织你的记忆单元。"
              />
            )}
            {spaces.length > 0 && filteredSpaces.length === 0 && (
              <EmptyState
                icon="search_off"
                title="没有匹配的空间"
                description={`没有找到包含 "${searchFilter}" 的空间。`}
              />
            )}
            <div className="space-y-2">
              {filteredSpaces.map((sp) => {
                const isActive = selectedSpace?.name === sp.name;
                return (
                  <div
                    key={sp.name}
                    onClick={() => setSelectedSpace(sp)}
                    className={[
                      "bg-surface border rounded-lg p-3 transition-colors cursor-pointer",
                      isActive
                        ? "border-primary bg-primary-fixed/30 shadow-sm"
                        : "border-border hover:border-primary/40",
                    ].join(" ")}
                  >
                    <div className="flex items-start gap-2">
                      <Icon
                        name="workspaces"
                        className={[
                          "text-[20px] flex-shrink-0 mt-0.5",
                          isActive ? "text-primary" : "text-primary/70",
                        ].join(" ")}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span
                            className={[
                              "text-body-md font-medium truncate",
                              isActive ? "text-primary" : "text-on-surface",
                            ].join(" ")}
                            title={sp.name}
                          >
                            {sp.name}
                          </span>
                          {sp.name.startsWith("default_") && (
                            <Pill variant="info" size="sm">系统</Pill>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-label-sm text-on-surface-variant">
                          <span className="flex items-center gap-1">
                            <Icon name="memory" className="text-[14px]" />
                            {sp.unit_count} 单元
                          </span>
                          {sp.child_spaces.length > 0 && (
                            <span className="flex items-center gap-1">
                              <Icon name="workspaces" className="text-[14px]" />
                              {sp.child_spaces.length} 子空间
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    {/* 快速操作 */}
                    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(sp.name, false);
                        }}
                        disabled={sp.unit_count > 0 || sp.child_spaces.length > 0}
                        className="text-label-sm text-error hover:underline disabled:opacity-40 disabled:cursor-not-allowed disabled:no-underline"
                        title={
                          sp.unit_count > 0 || sp.child_spaces.length > 0
                            ? "空间非空，请使用级联删除"
                            : "删除空空间"
                        }
                      >
                        删除
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(sp.name, true);
                        }}
                        className="text-label-sm text-error hover:underline"
                        title="删除空间及其所有单元"
                      >
                        级联删除
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* 右侧：空间详情 */}
        {selectedSpace && (
          <aside className="w-full md:w-[28rem] xl:w-[32rem] flex-shrink-0 flex flex-col bg-surface-bright overflow-hidden border-l border-border">
            {/* 详情头部（固定） */}
            <div className="flex-shrink-0 px-5 py-4 border-b border-border">
              <div className="flex items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <Icon name="workspaces" className="text-primary text-[20px] flex-shrink-0" />
                  <h3 className="text-body-lg font-bold text-on-surface truncate" title={selectedSpace.name}>
                    {selectedSpace.name}
                  </h3>
                  {selectedSpace.name.startsWith("default_") && (
                    <Pill variant="info" size="sm">系统</Pill>
                  )}
                </div>
                <button
                  onClick={() => setSelectedSpace(null)}
                  className="p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded"
                  title="关闭详情"
                >
                  <Icon name="close" className="text-[18px]" />
                </button>
              </div>
              <div className="flex items-center gap-3 text-label-md text-on-surface-variant">
                <span className="flex items-center gap-1">
                  <Icon name="memory" className="text-[16px]" />
                  <strong className="text-on-surface">{selectedSpace.unit_count}</strong> 单元
                </span>
                {selectedSpace.child_spaces.length > 0 && (
                  <span className="flex items-center gap-1">
                    <Icon name="workspaces" className="text-[16px]" />
                    <strong className="text-on-surface">{selectedSpace.child_spaces.length}</strong> 子空间
                  </span>
                )}
              </div>
            </div>

            {/* 详情内容（可滚动） */}
            <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-4 space-y-4">
              {/* 元数据 */}
              {selectedSpace.metadata && Object.keys(selectedSpace.metadata).length > 0 && (
                <section>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Icon name="info" className="text-on-surface-variant text-[16px]" />
                    <p className="text-label-md font-bold text-on-surface-variant">元数据</p>
                  </div>
                  <pre className="text-body-sm bg-surface border border-border p-3 rounded-lg overflow-x-auto whitespace-pre-wrap break-all">
                    {JSON.stringify(selectedSpace.metadata, null, 2)}
                  </pre>
                </section>
              )}

              {/* 摘要 */}
              {selectedSpace.summary && (
                <section>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Icon name="description" className="text-on-surface-variant text-[16px]" />
                    <p className="text-label-md font-bold text-on-surface-variant">摘要</p>
                  </div>
                  <div className="bg-surface border border-border rounded-lg p-3">
                    <p className="text-body-md text-on-surface whitespace-pre-wrap break-words">
                      {selectedSpace.summary}
                    </p>
                  </div>
                </section>
              )}

              {/* 子空间 */}
              {selectedSpace.child_spaces.length > 0 && (
                <section>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Icon name="workspaces" className="text-on-surface-variant text-[16px]" />
                    <p className="text-label-md font-bold text-on-surface-variant">
                      子空间 ({selectedSpace.child_spaces.length})
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selectedSpace.child_spaces.map((c) => (
                      <span
                        key={c}
                        className="px-2 py-1 bg-primary-fixed text-primary rounded text-label-sm border border-primary/20"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </section>
              )}

              {/* 空间内单元 */}
              <section>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <Icon name="memory" className="text-on-surface-variant text-[16px]" />
                    <p className="text-label-md font-bold text-on-surface-variant">
                      空间内单元 ({unitsInSpace.length})
                    </p>
                  </div>
                  <button
                    onClick={() => setShowAddUnit(!showAddUnit)}
                    className="text-label-sm text-primary hover:underline flex items-center gap-1"
                  >
                    <Icon name={showAddUnit ? "close" : "add"} className="text-[14px]" />
                    {showAddUnit ? "取消" : "添加单元"}
                  </button>
                </div>

                {/* 添加单元表单 */}
                {showAddUnit && (
                  <div className="bg-surface border border-border rounded-lg p-3 mb-3 space-y-2">
                    <input
                      type="text"
                      value={newUnitUid}
                      onChange={(e) => setNewUnitUid(e.target.value)}
                      placeholder="单元 UID（唯一标识）"
                      className="w-full px-3 py-1.5 rounded border border-border bg-surface-container-low text-on-surface text-body-sm focus:outline-none focus:border-primary"
                    />
                    <textarea
                      value={newUnitText}
                      onChange={(e) => setNewUnitText(e.target.value)}
                      placeholder="记忆文本内容"
                      rows={2}
                      className="w-full px-3 py-1.5 rounded border border-border bg-surface-container-low text-on-surface text-body-sm focus:outline-none focus:border-primary resize-none"
                    />
                    <button
                      onClick={handleAddUnit}
                      disabled={!newUnitUid.trim() || !newUnitText.trim()}
                      className="w-full bg-primary text-on-primary px-3 py-1.5 rounded text-label-md font-bold hover:bg-opacity-90 disabled:opacity-50"
                    >
                      创建并加入空间
                    </button>
                  </div>
                )}

                {/* 单元列表 */}
                {unitsLoading ? (
                  <Loading size="sm" label="加载单元..." />
                ) : unitsInSpace.length === 0 ? (
                  <div className="bg-surface-container-low rounded-lg p-4 text-center">
                    <p className="text-body-sm text-on-surface-variant">
                      {showAddUnit ? "填写表单添加第一个单元" : "该空间下还没有单元"}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {unitsInSpace.map((u) => (
                      <div
                        key={u.uid}
                        className="bg-surface border border-border rounded-lg p-2.5 group"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-label-md font-mono text-on-surface truncate" title={u.uid}>
                              {u.uid}
                            </p>
                            <p className="text-body-sm text-on-surface-variant line-clamp-2 mt-0.5">
                              {u.text || "(无文本)"}
                            </p>
                          </div>
                          <button
                            onClick={() => handleRemoveUnit(u.uid)}
                            className="opacity-0 group-hover:opacity-100 transition-opacity text-error hover:bg-error/10 p-1 rounded flex-shrink-0"
                            title="从空间移除"
                          >
                            <Icon name="link_off" className="text-[16px]" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* 危险操作区 */}
              <section className="pt-4 border-t border-border">
                <p className="text-label-md font-bold text-error mb-2 flex items-center gap-1">
                  <Icon name="warning" className="text-[16px]" />
                  危险操作
                </p>
                <div className="flex flex-col gap-2">
                  <button
                    onClick={() => handleDelete(selectedSpace.name, false)}
                    disabled={selectedSpace.unit_count > 0 || selectedSpace.child_spaces.length > 0}
                    className="px-3 py-2 text-left border border-error/30 text-error rounded-lg text-body-sm hover:bg-error/5 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <Icon name="delete" className="text-[16px] inline -mt-0.5 mr-1" />
                    删除空间
                    <span className="text-label-sm text-on-surface-variant ml-2">
                      (空空间才能删除)
                    </span>
                  </button>
                  <button
                    onClick={() => handleDelete(selectedSpace.name, true)}
                    className="px-3 py-2 text-left border border-error text-error rounded-lg text-body-sm bg-error/5 hover:bg-error/10"
                  >
                    <Icon name="delete_forever" className="text-[16px] inline -mt-0.5 mr-1" />
                    级联删除空间及所有单元
                    <span className="text-label-sm text-on-surface-variant ml-2">
                      (不可恢复)
                    </span>
                  </button>
                </div>
              </section>
            </div>
          </aside>
        )}
      </div>
    </AppShell>
  );
}
