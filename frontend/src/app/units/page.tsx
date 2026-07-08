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

  return (
    <AppShell title="记忆单元" subtitle="记忆单元管理">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">
          {/* 操作栏 */}
          <div className="flex items-center justify-between">
            <h3 className="text-body-lg font-bold text-on-surface">
              记忆单元列表 ({units.length})
            </h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => listUnits(100, 0)}
                className="text-label-md text-primary hover:underline flex items-center gap-1"
              >
                <Icon name="refresh" className="text-[14px]" /> 刷新
              </button>
              <button
                onClick={() => setShowCreate(!showCreate)}
                className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:bg-opacity-90 transition-all flex items-center gap-1"
              >
                <Icon name="add" className="text-[16px]" /> 添加单元
              </button>
            </div>
          </div>

          {/* 创建表单 */}
          {showCreate && (
            <section className="bg-surface border border-border rounded-xl p-5 space-y-3">
              <h4 className="text-body-md font-bold text-on-surface">添加记忆单元</h4>
              <input
                type="text"
                value={newUid}
                onChange={(e) => setNewUid(e.target.value)}
                placeholder="单元 UID（唯一标识，如 msg_001）"
                className="w-full px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
              />
              <textarea
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                placeholder="记忆文本内容"
                rows={3}
                className="w-full px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary resize-none"
              />
              <input
                type="text"
                value={newSpace}
                onChange={(e) => setNewSpace(e.target.value)}
                placeholder="空间名称（可选）"
                className="w-full px-4 py-2 rounded-lg border border-border bg-surface-container-low text-on-surface focus:outline-none focus:border-primary"
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCreate}
                  disabled={!newUid.trim() || !newText.trim() || isLoading}
                  className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-body-sm hover:bg-opacity-90 disabled:opacity-50"
                >
                  创建
                </button>
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 rounded-lg text-body-sm text-on-surface-variant hover:bg-surface-container-low"
                >
                  取消
                </button>
              </div>
            </section>
          )}

          {/* 单元列表 */}
          {isLoading && units.length === 0 && <Loading size="md" label="加载中..." />}
          {!isLoading && units.length === 0 && !showCreate && (
            <EmptyState
              icon="memory"
              title="暂无记忆单元"
              description="添加一个记忆单元，或通过文档导入构建记忆。"
            />
          )}
          <div className="space-y-2">
            {units.map((u) => (
              <div
                key={u.uid}
                className="bg-surface border border-border rounded-lg p-4 hover:border-primary/40 transition-colors cursor-pointer"
                onClick={() => setSelectedUnit(u)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Icon name="memory" className="text-primary text-[18px]" />
                      <span className="text-body-md font-medium text-on-surface truncate">
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
                    className="text-error hover:bg-error/10 p-1 rounded"
                  >
                    <Icon name="delete" className="text-[18px]" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* 单元详情 */}
          {selectedUnit && (
            <section className="bg-surface border border-border rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-body-lg font-bold text-on-surface">
                  单元详情: {selectedUnit.uid}
                </h3>
                <button
                  onClick={() => setSelectedUnit(null)}
                  className="text-label-md text-on-surface-variant hover:text-on-surface"
                >
                  关闭
                </button>
              </div>
              <div className="space-y-3">
                <div>
                  <p className="text-body-sm text-on-surface-variant mb-1">文本内容</p>
                  <p className="text-body-md text-on-surface whitespace-pre-wrap">
                    {selectedUnit.text}
                  </p>
                </div>
                {Object.keys(selectedUnit.raw_data).length > 1 && (
                  <div>
                    <p className="text-body-sm text-on-surface-variant mb-1">原始数据</p>
                    <pre className="text-body-sm bg-surface-container-low p-3 rounded-lg overflow-x-auto">
                      {JSON.stringify(selectedUnit.raw_data, null, 2)}
                    </pre>
                  </div>
                )}
                {Object.keys(selectedUnit.metadata).length > 0 && (
                  <div>
                    <p className="text-body-sm text-on-surface-variant mb-1">元数据</p>
                    <pre className="text-body-sm bg-surface-container-low p-3 rounded-lg overflow-x-auto">
                      {JSON.stringify(selectedUnit.metadata, null, 2)}
                    </pre>
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
