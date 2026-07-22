"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { EmptyState } from "@/components/shared/EmptyState";
import { Pill } from "@/components/shared/Pill";
import { api, ApiError } from "@/services/api";
import type { MandolUnitInfo } from "@/types";

type SummaryItem = MandolUnitInfo & {
  summary?: string;
  keywords?: string[];
  source_doc?: string;
  section?: string;
  generated_at?: string;
};

export default function SummariesPage() {
  const [items, setItems] = useState<SummaryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SummaryItem | null>(null);
  const [keyword, setKeyword] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIsLoading(true);
      setError(null);
      try {
        const r = await api.get<{ total: number; items: MandolUnitInfo[] }>(
          "mandol/summaries?limit=500",
        );
        if (cancelled) return;
        setItems((r.items || []) as SummaryItem[]);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : "加载摘要失败");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = items.filter((it) => {
    if (!keyword.trim()) return true;
    const k = keyword.toLowerCase();
    return (
      (it.text || "").toLowerCase().includes(k) ||
      (it.summary || "").toLowerCase().includes(k) ||
      (it.uid || "").toLowerCase().includes(k) ||
      ((it.keywords || []).join(" ")).toLowerCase().includes(k)
    );
  });

  return (
    <AppShell>
      <div className="p-6 max-w-6xl mx-auto">
        <header className="mb-6 flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center">
            <Icon name="summarize" filled className="text-[24px]" />
          </div>
          <div className="flex-1">
            <h1 className="text-headline-md font-bold text-on-surface">摘要详情</h1>
            <p className="text-body-md text-on-surface-variant">
              共 {items.length} 条摘要（由 build_high_level 自动生成的 episodic_summary 空间单元）
            </p>
          </div>
          <a
            href="/"
            className="text-body-md text-primary hover:underline flex items-center gap-1"
          >
            <Icon name="arrow_back" className="text-[16px]" />
            返回仪表盘
          </a>
        </header>

        <div className="mb-4 flex items-center gap-3">
          <div className="flex-1 relative">
            <Icon
              name="search"
              className="text-[18px] text-on-surface-variant absolute left-3 top-1/2 -translate-y-1/2"
            />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索摘要内容、UID 或关键词"
              className="w-full pl-10 pr-3 py-2 rounded-lg border border-border bg-surface-container-low text-body-md focus:outline-none focus:border-primary"
            />
          </div>
          <Pill variant="default" size="md">
            显示 {filtered.length} / {items.length}
          </Pill>
        </div>

        {isLoading ? (
          <Loading label="加载摘要..." />
        ) : error ? (
          <div className="rounded-xl border border-error/30 bg-error/5 p-4 text-error">
            {error}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon="summarize"
            title={items.length === 0 ? "尚无摘要" : "没有匹配的摘要"}
            description={
              items.length === 0
                ? "上传文档并执行「记忆构建」后，系统将自动生成摘要。"
                : "请尝试其他关键词。"
            }
          />
        ) : (
          <div className="space-y-3">
            {filtered.map((it) => (
              <button
                key={it.uid}
                type="button"
                onClick={() => setSelected(it)}
                className="w-full text-left rounded-xl border border-border bg-surface hover:border-primary/40 hover:bg-primary-container/30 p-4 transition-all"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon name="article" className="text-[16px] text-primary" />
                  <span className="text-body-md font-bold text-on-surface line-clamp-1">
                    {it.summary || it.text || it.uid}
                  </span>
                </div>
                <p className="text-body-md text-on-surface-variant line-clamp-2">
                  {it.text || it.summary}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-label-md text-on-surface-variant">
                  <Pill variant="default" size="sm">
                    {it.space_name || "episodic_summary"}
                  </Pill>
                  {(it.keywords || []).slice(0, 5).map((kw) => (
                    <Pill key={kw} variant="primary" size="sm">
                      {kw}
                    </Pill>
                  ))}
                  {it.generated_at && (
                    <span className="ml-auto">
                      {new Date(it.generated_at).toLocaleString("zh-CN")}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {selected && (
        <div
          className="fixed inset-0 z-[100] bg-black/40 flex items-center justify-center p-4"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-surface border border-border rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-y-auto p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-4">
              <Icon name="summarize" filled className="text-[22px] text-primary" />
              <h2 className="text-title-md font-bold text-on-surface flex-1">
                摘要详情
              </h2>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="w-8 h-8 rounded-lg hover:bg-surface-container-high flex items-center justify-center text-on-surface-variant"
              >
                <Icon name="close" className="text-[18px]" />
              </button>
            </div>
            <div className="space-y-3 text-body-md text-on-surface">
              <div>
                <div className="text-label-md text-on-surface-variant mb-1">UID</div>
                <code className="text-body-md font-mono text-on-surface break-all">
                  {selected.uid}
                </code>
              </div>
              {selected.summary && (
                <div>
                  <div className="text-label-md text-on-surface-variant mb-1">摘要</div>
                  <p className="text-body-lg font-medium text-on-surface leading-relaxed">
                    {selected.summary}
                  </p>
                </div>
              )}
              {selected.text && (
                <div>
                  <div className="text-label-md text-on-surface-variant mb-1">原文</div>
                  <p className="text-body-md text-on-surface whitespace-pre-wrap leading-relaxed">
                    {selected.text}
                  </p>
                </div>
              )}
              {selected.keywords && selected.keywords.length > 0 && (
                <div>
                  <div className="text-label-md text-on-surface-variant mb-1">关键词</div>
                  <div className="flex flex-wrap gap-1">
                    {selected.keywords.map((kw) => (
                      <Pill key={kw} variant="primary" size="sm">
                        {kw}
                      </Pill>
                    ))}
                  </div>
                </div>
              )}
              <div className="grid grid-cols-2 gap-2 text-label-md text-on-surface-variant pt-2">
                {selected.source_doc && (
                  <div>
                    <span>来源文档：</span>
                    <span className="text-on-surface">{selected.source_doc}</span>
                  </div>
                )}
                {selected.section && (
                  <div>
                    <span>章节：</span>
                    <span className="text-on-surface">{selected.section}</span>
                  </div>
                )}
                {selected.generated_at && (
                  <div>
                    <span>生成时间：</span>
                    <span className="text-on-surface">
                      {new Date(selected.generated_at).toLocaleString("zh-CN")}
                    </span>
                  </div>
                )}
                {selected.space_name && (
                  <div>
                    <span>空间：</span>
                    <span className="text-on-surface">{selected.space_name}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
