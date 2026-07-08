"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { api, ApiError } from "@/services/api";
import type { MandolStatsResponse, MandolUnitInfo } from "@/types";

/* ─── 横向统计卡片 ─── */
function StatCard({
  icon,
  label,
  value,
  sub,
  accent = "primary",
  href,
}: {
  icon: string;
  label: string;
  value: string | number;
  sub?: string;
  accent?: "primary" | "success" | "warning" | "info" | "default";
  href?: string;
}) {
  const colors: Record<string, string> = {
    primary: "bg-primary-fixed text-primary",
    success: "bg-success/10 text-success",
    warning: "bg-warning/10 text-warning",
    info: "bg-info/10 text-info",
    default: "bg-surface-container text-on-surface-variant",
  };

  const inner = (
    <div className="bg-surface border border-border rounded-2xl p-5 hover:border-primary/50 hover:shadow-md transition-all cursor-pointer group h-full">
      <div className="flex items-center gap-4">
        <div className={`w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0 ${colors[accent]}`}>
          <Icon name={icon} filled className="text-[28px]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-display-sm font-bold text-on-surface leading-none">{value}</p>
          <p className="text-body-md font-medium text-on-surface mt-1">{label}</p>
          {sub && <p className="text-label-md text-on-surface-variant mt-0.5">{sub}</p>}
        </div>
        {href && (
          <Icon
            name="arrow_forward"
            className="text-on-surface-variant group-hover:text-primary transition-colors text-[20px] flex-shrink-0"
          />
        )}
      </div>
    </div>
  );

  if (href) return <Link href={href} className="block h-full">{inner}</Link>;
  return inner;
}

/* ── 快速入口 ─── */
function QuickAction({
  icon,
  title,
  desc,
  href,
}: {
  icon: string;
  title: string;
  desc: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="bg-surface border border-border rounded-2xl p-4 hover:border-primary hover:shadow-md transition-all group flex items-center gap-3"
    >
      <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center flex-shrink-0">
        <Icon name={icon} filled className="text-[22px]" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-body-lg font-bold text-on-surface">{title}</p>
        <p className="text-body-sm text-on-surface-variant">{desc}</p>
      </div>
      <Icon
        name="arrow_forward"
        className="text-on-surface-variant group-hover:text-primary transition-colors text-[20px] flex-shrink-0"
      />
    </Link>
  );
}

/* ─── 最近单元列表 ─── */
function RecentUnit({ unit }: { unit: MandolUnitInfo }) {
  const raw = unit.raw_data as Record<string, string> | undefined;
  const meta = unit.metadata as Record<string, string> | undefined;
  const name = raw?.entity_name || raw?.event_name || unit.uid;
  const type = meta?.type || meta?.category || "单元";
  return (
    <Link
      href={`/units?uid=${encodeURIComponent(unit.uid)}`}
      className="block p-3 rounded-xl hover:bg-surface-container-low transition-colors group"
    >
      <div className="flex items-center gap-3">
        <Icon
          name={type === "entity" ? "person" : type === "event" ? "event" : "description"}
          className="text-on-surface-variant group-hover:text-primary text-[20px] flex-shrink-0"
        />
        <div className="flex-1 min-w-0">
          <p className="text-body-md font-medium text-on-surface truncate">{name}</p>
          <p className="text-label-md text-on-surface-variant truncate">{unit.text}</p>
        </div>
        <Pill size="sm" variant="info">{type}</Pill>
      </div>
    </Link>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<MandolStatsResponse | null>(null);
  const [recentUnits, setRecentUnits] = useState<MandolUnitInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [s, units] = await Promise.all([
          api.get<MandolStatsResponse>("mandol/stats"),
          api
            .get<{ total: number; items: MandolUnitInfo[] }>("mandol/units?limit=8")
            .catch(() => ({ total: 0, items: [] })),
        ]);
        setStats(s);
        setRecentUnits(units.items || []);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "加载失败");
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const quickActions = [
    { icon: "search", title: "记忆检索", desc: "多策略全息检索", href: "/search" },
    { icon: "smart_toy", title: "智能问答", desc: "基于记忆的对话", href: "/chat" },
    { icon: "upload_file", title: "文档导入", desc: "PDF / DOCX / MD", href: "/import" },
    { icon: "build", title: "记忆构建", desc: "提取实体与事件", href: "/build" },
    { icon: "account_tree", title: "知识图谱", desc: "图谱浏览与溯源", href: "/graph" },
    { icon: "settings", title: "系统设置", desc: "模型与参数配置", href: "/settings" },
  ];

  return (
    <AppShell title="仪表盘" subtitle="Mandol 记忆平台总览">
      <div className="flex-1 overflow-y-auto custom-scrollbar w-full">
        <div className="px-8 py-6 space-y-5">
          {error && (
            <div className="bg-error/10 border border-error/20 text-error rounded-xl p-4 flex items-center gap-2">
              <Icon name="error" filled />
              <span className="text-body-md">{error}</span>
            </div>
          )}

          {isLoading && !stats && <Loading size="lg" label="加载仪表盘..." />}

          {stats && (
            <>
              {/* ── 核心指标卡片：6列平铺 ── */}
              <section className="grid grid-cols-2 md:grid-cols-3 2xl:grid-cols-6 gap-4">
                <StatCard icon="memory" label="记忆单元" value={stats.total_units || 0} sub="总计" accent="primary" href="/units" />
                <StatCard icon="hub" label="记忆空间" value={stats.total_spaces || 0} sub="总计" accent="info" href="/spaces" />
                <StatCard icon="person" label="实体" value={stats.entity_count || 0} sub="已提取" accent="success" href="/entities" />
                <StatCard icon="event" label="事件" value={stats.event_count || 0} sub="已提取" accent="warning" href="/events" />
                <StatCard icon="summarize" label="摘要" value={stats.summary_count || 0} sub="已生成" accent="primary" href="/build" />
                <StatCard icon="account_tree" label="基础记忆" value={stats.base_memory_count || 0} sub="图谱节点" accent="default" href="/graph" />
              </section>

              {/* ── 第二行：Token + 系统状态 + 快速操作（三列平铺） ── */}
              <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Token 用量 */}
                <div className="bg-surface border border-border rounded-2xl p-5">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center">
                      <Icon name="token" filled className="text-[20px]" />
                    </div>
                    <h3 className="text-body-lg font-bold text-on-surface">Token 用量</h3>
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-baseline justify-between">
                      <span className="text-body-sm text-on-surface-variant">输入</span>
                      <span className="text-headline-md font-bold text-on-surface">
                        {(stats.token_usage?.prompt_tokens ?? 0).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex items-baseline justify-between">
                      <span className="text-body-sm text-on-surface-variant">输出</span>
                      <span className="text-headline-md font-bold text-on-surface">
                        {(stats.token_usage?.completion_tokens ?? 0).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex items-baseline justify-between border-t border-border pt-3">
                      <span className="text-body-md font-medium text-on-surface-variant">总计</span>
                      <span className="text-display-sm font-bold text-primary">
                        {(stats.token_usage?.total_tokens ?? 0).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 系统状态 */}
                <div className="bg-surface border border-border rounded-2xl p-5">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-xl bg-info/10 text-info flex items-center justify-center">
                      <Icon name="info" filled className="text-[20px]" />
                    </div>
                    <h3 className="text-body-lg font-bold text-on-surface">系统状态</h3>
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-body-md text-on-surface-variant">引擎</span>
                      <Pill variant={stats.enabled ? "success" : "default"} size="md">
                        {stats.enabled ? "已启用" : "未启用"}
                      </Pill>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-body-md text-on-surface-variant">数据状态</span>
                      <Pill variant={stats.dirty ? "warning" : "success"} size="md">
                        {stats.dirty ? "有未保存变更" : "已同步"}
                      </Pill>
                    </div>
                    {stats.error && (
                      <div className="flex items-center justify-between">
                        <span className="text-body-md text-on-surface-variant">错误</span>
                        <Pill variant="error" size="md">{stats.error}</Pill>
                      </div>
                    )}
                  </div>
                </div>

                {/* 快速操作 - 网格布局 */}
                <div className="bg-surface border border-border rounded-2xl p-5">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-xl bg-warning/10 text-warning flex items-center justify-center">
                      <Icon name="bolt" filled className="text-[20px]" />
                    </div>
                    <h3 className="text-body-lg font-bold text-on-surface">快速操作</h3>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {quickActions.map((a) => (
                      <Link
                        key={a.href}
                        href={a.href}
                        className="flex items-center gap-2 p-2 rounded-lg hover:bg-surface-container-low transition-colors group"
                      >
                        <div className="w-8 h-8 rounded-lg bg-primary-fixed text-primary flex items-center justify-center flex-shrink-0">
                          <Icon name={a.icon} filled className="text-[16px]" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-body-sm font-bold text-on-surface truncate">{a.title}</p>
                          <p className="text-label-sm text-on-surface-variant truncate">{a.desc}</p>
                        </div>
                      </Link>
                    ))}
                  </div>
                </div>
              </section>

              {/* ── 最近记忆单元（全宽） ── */}
              <section className="bg-surface border border-border rounded-2xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center">
                      <Icon name="history" filled className="text-[20px]" />
                    </div>
                    <h3 className="text-body-lg font-bold text-on-surface">最近记忆单元</h3>
                  </div>
                  <Link
                    href="/units"
                    className="text-body-sm text-primary hover:underline flex items-center gap-1"
                  >
                    查看全部 <Icon name="arrow_forward" className="text-[14px]" />
                  </Link>
                </div>
                {recentUnits.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
                    {recentUnits.map((u) => {
                      const raw = u.raw_data as Record<string, string> | undefined;
                      const meta = u.metadata as Record<string, string> | undefined;
                      const name = raw?.entity_name || raw?.event_name || u.uid;
                      const type = meta?.type || meta?.category || "单元";
                      return (
                        <Link
                          key={u.uid}
                          href={`/units?uid=${encodeURIComponent(u.uid)}`}
                          className="block p-4 rounded-xl bg-surface-container-low hover:bg-surface-container-high hover:border-primary transition-all group border border-transparent"
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <Icon
                              name={type === "entity" ? "person" : type === "event" ? "event" : "description"}
                              className="text-on-surface-variant group-hover:text-primary text-[18px] flex-shrink-0"
                            />
                            <p className="text-body-md font-bold text-on-surface truncate">{name}</p>
                          </div>
                          <p className="text-label-md text-on-surface-variant line-clamp-2">{u.text}</p>
                          <div className="mt-2">
                            <Pill size="sm" variant="info">{type}</Pill>
                          </div>
                        </Link>
                      );
                    })}
                  </div>
                ) : (
                  <EmptyState
                    icon="inbox"
                    title="暂无记忆单元"
                    description="上传文档或手动创建单元开始构建记忆。"
                    action={
                      <Link href="/import" className="text-body-md text-primary hover:underline">
                        上传文档 →
                      </Link>
                    }
                  />
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
