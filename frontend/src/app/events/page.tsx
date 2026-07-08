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

export default function EventsPage() {
  const { units, isLoading, error, listUnits } = useMandol();
  const [query, setQuery] = useState("");
  const [selectedUnit, setSelectedUnit] = useState<MandolUnitInfo | null>(null);

  useEffect(() => {
    listUnits(500);
  }, [listUnits]);

  // 过滤出事件类型的单元
  const events = units.filter(
    (u) => u.metadata?.type === "event" || u.raw_data?.event_name || u.metadata?.category === "event_causal"
  );

  const filtered = query
    ? events.filter(
        (e) =>
          (e.raw_data?.event_name || e.uid).toLowerCase().includes(query.toLowerCase()) ||
          (e.text || "").toLowerCase().includes(query.toLowerCase()),
      )
    : events;

  return (
    <AppShell title="事件" subtitle="浏览提取的事件和因果关系">
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
                placeholder="搜索事件..."
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

          {isLoading && <Loading label="加载事件中..." />}

          {!isLoading && filtered.length === 0 && !error && (
            <EmptyState
              icon="event"
              title="未找到事件"
              description="请先上传文档到记忆库并执行记忆构建，系统将自动提取事件。"
              action={
                <Link href="/build" className="text-primary hover:underline">
                  前往记忆构建
                </Link>
              }
            />
          )}

          {/* 事件列表 */}
          {!isLoading && filtered.length > 0 && (
            <div className="space-y-4">
              {filtered.map((event) => {
                const name = event.raw_data?.event_name || event.uid;
                const description = event.raw_data?.event_description || event.raw_data?.description || "";
                return (
                  <div
                    key={event.uid}
                    onClick={() => setSelectedUnit(event)}
                    className="bg-surface border border-border rounded-xl p-5 hover:border-primary transition-all cursor-pointer"
                  >
                    <div className="flex items-start gap-3 mb-3">
                      <Icon name="event" className="text-primary text-[24px] mt-0.5" />
                      <div className="flex-1">
                        <h3 className="text-body-lg font-bold text-on-surface mb-1">{name}</h3>
                        {description && (
                          <p className="text-body-md text-on-surface-variant line-clamp-2">{description}</p>
                        )}
                      </div>
                    </div>
                    <p className="text-body-sm text-on-surface-variant line-clamp-3 mb-3">{event.text}</p>
                    <div className="flex items-center justify-between">
                      <span className="text-label-sm text-outline font-mono">{event.uid}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          window.location.href = `/causal?event=${encodeURIComponent(event.uid)}`;
                        }}
                        className="text-primary hover:underline text-label-md flex items-center gap-1"
                      >
                        <Icon name="account_tree" className="text-[16px]" />
                        追踪因果链
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* 事件详情弹窗 */}
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
                    <Icon name="event" className="text-primary text-[32px]" />
                    <div>
                      <h2 className="text-headline-md font-bold text-on-surface">
                        {selectedUnit.raw_data?.event_name || selectedUnit.uid}
                      </h2>
                      <p className="text-body-md text-on-surface-variant">
                        {selectedUnit.raw_data?.event_description || selectedUnit.raw_data?.description || ""}
                      </p>
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
                    <h3 className="text-body-md font-bold text-on-surface mb-2">事件详情</h3>
                    <p className="text-body-md text-on-surface-variant">{selectedUnit.text}</p>
                  </div>

                  <div>
                    <h3 className="text-body-md font-bold text-on-surface mb-2">元数据</h3>
                    <pre className="text-label-md font-mono text-on-surface-variant bg-surface-container-low p-3 rounded overflow-x-auto">
                      {JSON.stringify(selectedUnit.metadata, null, 2)}
                    </pre>
                  </div>

                  <div className="flex gap-2">
                    <Link
                      href={`/causal?event=${encodeURIComponent(selectedUnit.uid)}`}
                      className="flex-1 bg-primary text-on-primary py-2 rounded-lg font-bold text-body-md hover:opacity-90 transition-all flex items-center justify-center gap-2"
                    >
                      <Icon name="account_tree" className="text-[18px]" />
                      追踪因果链
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
