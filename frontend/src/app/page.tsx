"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { api, ApiError } from "@/services/api";
import type { MandolStatsResponse, MandolUnitInfo, ExternalStoreStatus } from "@/types";

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
  const [external, setExternal] = useState<ExternalStoreStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clearTarget, setClearTarget] = useState<null | {
    key: string;
    title: string;
    message: string;
    endpoint: string;
    danger?: boolean;
  }>(null);
  const [clearing, setClearing] = useState(false);
  const [toast, setToast] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const refreshStats = useCallback(async () => {
    try {
      const s = await api.get<MandolStatsResponse>("mandol/stats/quick");
      setStats(s as unknown as MandolStatsResponse);
      const ext = await api.get<ExternalStoreStatus>("mandol/external-store-status");
      setExternal(ext);
      const units = await api.get<{ total: number; items: MandolUnitInfo[] }>(
        "mandol/units?limit=8"
      );
      setRecentUnits(units.items || []);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    (async () => {
      setIsLoading(true);
      setError(null);
      try {
        // 仪表盘首屏：只拉快接口 /stats/quick（带 5s 进程内缓存，~10ms 内返回）
        const s = await api.get<MandolStatsResponse>("mandol/stats/quick");
        setStats(s as unknown as MandolStatsResponse);
        setIsLoading(false);
        // 详情数据放后台拉，不阻塞首屏
        api
          .get<{ total: number; items: MandolUnitInfo[] }>("mandol/units?limit=8")
          .then((units) => setRecentUnits(units.items || []))
          .catch(() => {});
        api
          .get<ExternalStoreStatus>("mandol/external-store-status")
          .then((ext) => setExternal(ext))
          .catch(() => {});
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "加载失败");
        setIsLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const handleConfirmClear = useCallback(async () => {
    if (!clearTarget) return;
    setClearing(true);
    try {
      // 清空"所有"是后台任务, 提交后立即返回 running;
      // 其他细粒度清空是同步接口, 等待返回即可。
      if (clearTarget.endpoint === "clear-everything") {
        await api.post<{ status: string; message?: string }>(
          "mandol/clear-everything",
          {}
        );
        // 轮询 clear-status 直到 completed / failed
        const startedAt = Date.now();
        const poll = async (): Promise<{ status: string; message: string }> => {
          const r = await api.get<{
            status: string;
            message: string;
            elapsed_seconds: number;
          }>("mandol/clear-status");
          if (r.status === "completed" || r.status === "failed") return r;
          if (Date.now() - startedAt > 120_000) {
            return { status: "failed", message: "清空超时(>120s)" };
          }
          await new Promise((res) => setTimeout(res, 1000));
          return poll();
        };
        const final = await poll();
        if (final.status === "completed") {
          setToast({ kind: "success", text: `已清空：${clearTarget.title}\n${final.message}` });
        } else {
          setToast({ kind: "error", text: `清空失败：${final.message}` });
        }
      } else {
        await api.post<{ status: string; message?: string }>(
          `mandol/${clearTarget.endpoint}`,
          {}
        );
        setToast({ kind: "success", text: `已清空：${clearTarget.title}` });
      }
      setClearTarget(null);
      await refreshStats();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : String(err);
      setToast({ kind: "error", text: `清空失败：${msg}` });
    } finally {
      setClearing(false);
    }
  }, [clearTarget, refreshStats]);

  const quickActions = [
    { icon: "search", title: "记忆检索", desc: "多策略全息检索", href: "/search" },
    { icon: "smart_toy", title: "智能问答", desc: "基于记忆的对话", href: "/chat" },
    { icon: "upload_file", title: "文档导入", desc: "PDF / DOCX / MD", href: "/import" },
    { icon: "build", title: "记忆构建", desc: "提取实体与事件", href: "/build" },
    { icon: "account_tree", title: "知识图谱", desc: "图谱浏览与溯源", href: "/graph" },
    { icon: "settings", title: "系统设置", desc: "模型与参数配置", href: "/settings" },
  ];

  return (
    <AppShell title="仪表盘" subtitle="记忆平台总览">
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
                <StatCard icon="summarize" label="摘要" value={stats.summary_count || 0} sub="已生成" accent="primary" href="/summaries" />
                <StatCard icon="account_tree" label="基础记忆" value={stats.base_memory_count || 0} sub="图谱节点" accent="default" href="/graph" />
              </section>

              {/* ── 第二行：Token + 系统状态 + 外部存储 + 快速操作 ── */}
              <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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

                {/* 外部存储状态 */}
                {external && (
                  <div className="bg-surface border border-border rounded-2xl p-5">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-xl bg-secondary-container text-on-secondary-container flex items-center justify-center">
                        <Icon name="storage" filled className="text-[20px]" />
                      </div>
                      <h3 className="text-body-lg font-bold text-on-surface">外部存储</h3>
                    </div>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-body-md text-on-surface-variant flex items-center gap-1">
                          <Icon name="hub" className="text-[16px]" /> Neo4j
                        </span>
                        <Pill variant={external.neo4j.available ? "success" : "default"} size="md">
                          {external.neo4j.available
                            ? `${external.neo4j.nodes} 节点 · ${external.neo4j.edges} 边`
                            : "离线"}
                        </Pill>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-body-md text-on-surface-variant flex items-center gap-1">
                          <Icon name="database" className="text-[16px]" /> Milvus
                        </span>
                        <Pill variant={external.milvus.available ? "success" : "default"} size="md">
                          {external.milvus.available ? `${external.milvus.unit_count} 单元` : "离线"}
                        </Pill>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-body-md text-on-surface-variant flex items-center gap-1">
                          <Icon name="save" className="text-[16px]" /> Snapshot
                        </span>
                        <Pill variant={external.snapshot.exists ? "success" : "default"} size="md">
                          {external.snapshot.exists
                            ? `${(external.snapshot.size_bytes / 1024).toFixed(1)} KB`
                            : "未保存"}
                        </Pill>
                      </div>
                    </div>
                  </div>
                )}

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

              {/* ── 数据管理（全宽） ── */}
              <section className="bg-surface border border-border rounded-2xl p-5">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-error/10 text-error flex items-center justify-center">
                    <Icon name="delete_sweep" filled className="text-[20px]" />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-body-lg font-bold text-on-surface">数据管理</h3>
                    <p className="text-label-md text-on-surface-variant">
                      按类别清空记忆数据，操作不可恢复
                    </p>
                  </div>
                </div>

                {(() => {
                  const unitCount = (stats?.total_units as number) || 0;
                  const spaceCount = (stats?.total_spaces as number) || 0;
                  const entityCount = (stats?.entity_count as number) || 0;
                  const eventCount = (stats?.event_count as number) || 0;
                  const neo4jNodes = external?.neo4j?.nodes ?? 0;
                  const milvusRows = external?.milvus?.unit_count ?? 0;
                  const items: Array<{
                    key: string;
                    icon: string;
                    title: string;
                    desc: string;
                    count: number;
                    countLabel: string;
                    endpoint: string;
                    message: string;
                    disabled?: boolean;
                    disabledReason?: string;
                  }> = [
                    {
                      key: "units",
                      icon: "memory",
                      title: "记忆单元",
                      desc: "Milvus 向量 + Mandol 内存中的所有单元",
                      count: unitCount,
                      countLabel: "单元",
                      endpoint: "clear-units",
                      message: `将清空 ${unitCount} 个记忆单元及其向量索引，实体/事件节点保留。`,
                    },
                    {
                      key: "spaces",
                      icon: "hub",
                      title: "记忆空间",
                      desc: "所有 Mandol 空间（须先清空记忆单元）",
                      count: spaceCount,
                      countLabel: "空间",
                      endpoint: "clear-spaces",
                      message: `将清空 ${spaceCount} 个记忆空间。`,
                      disabled: unitCount > 0,
                      disabledReason: "请先清空记忆单元",
                    },
                    {
                      key: "entities",
                      icon: "person",
                      title: "实体",
                      desc: "Neo4j 中的实体节点 + Mandol 实体集合",
                      count: entityCount,
                      countLabel: "实体",
                      endpoint: "clear-entities",
                      message: `将清空 ${entityCount} 个实体节点。`,
                    },
                    {
                      key: "events",
                      icon: "event",
                      title: "事件",
                      desc: "Neo4j 中的事件节点 + Mandol 事件集合",
                      count: eventCount,
                      countLabel: "事件",
                      endpoint: "clear-events",
                      message: `将清空 ${eventCount} 个事件节点。`,
                    },
                    {
                      key: "summaries",
                      icon: "summarize",
                      title: "摘要",
                      desc: "vault 文件 frontmatter 中的 summary 字段",
                      count: 0,
                      countLabel: "摘要",
                      endpoint: "clear-summaries",
                      message: "将清空所有 vault 文档 frontmatter 中的 summary 字段。",
                    },
                    {
                      key: "base-memories",
                      icon: "folder",
                      title: "基础记忆",
                      desc: "data/vault/imports/ 下的解析文件",
                      count: 0,
                      countLabel: "目录",
                      endpoint: "clear-base-memories",
                      message: "将删除 data/vault/imports/ 下所有解析后的 md 文件及子目录。",
                    },
                    {
                      key: "neo4j",
                      icon: "account_tree",
                      title: "Neo4j",
                      desc: "整个 Neo4j 图（节点 + 关系）",
                      count: neo4jNodes,
                      countLabel: "节点",
                      endpoint: "clear-neo4j",
                      message: `将清空 Neo4j 全部 ${neo4jNodes} 个节点。`,
                    },
                    {
                      key: "milvus",
                      icon: "database",
                      title: "Milvus",
                      desc: "整个 Milvus 向量集合",
                      count: milvusRows,
                      countLabel: "向量",
                      endpoint: "clear-milvus",
                      message: `将 drop Milvus 集合（约 ${milvusRows} 条向量）。`,
                    },
                  ];

                  return (
                    <>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {items.map((it) => {
                          const disabled = !!it.disabled;
                          return (
                            <button
                              key={it.key}
                              type="button"
                              disabled={disabled || clearing}
                              onClick={() =>
                                setClearTarget({
                                  key: it.key,
                                  title: `清空${it.title}`,
                                  message: `${it.desc}\n\n${it.message}\n\n此操作不可恢复，请输入"确认"以继续。`,
                                  endpoint: it.endpoint,
                                  danger: true,
                                })
                              }
                              className={[
                                "text-left p-4 rounded-xl border transition-all group relative",
                                disabled
                                  ? "border-border bg-surface-container-low opacity-50 cursor-not-allowed"
                                  : "border-border bg-surface-container-low hover:bg-error/5 hover:border-error/40 cursor-pointer",
                              ].join(" ")}
                            >
                              <div className="flex items-start gap-3">
                                <div
                                  className={[
                                    "w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0",
                                    disabled
                                      ? "bg-surface-container text-on-surface-variant"
                                      : "bg-error/10 text-error group-hover:bg-error/15",
                                  ].join(" ")}
                                >
                                  <Icon name={it.icon} filled className="text-[20px]" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="text-body-md font-bold text-on-surface truncate">
                                    {it.title}
                                  </p>
                                  <p className="text-label-md text-on-surface-variant line-clamp-2">
                                    {it.desc}
                                  </p>
                                  <div className="mt-2 flex items-center gap-2">
                                    <Pill size="sm" variant={disabled ? "default" : "warning"}>
                                      {it.count} {it.countLabel}
                                    </Pill>
                                    {disabled && it.disabledReason && (
                                      <span className="text-label-sm text-error">
                                        {it.disabledReason}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>

                      <div className="mt-4 pt-4 border-t border-border flex items-center justify-between gap-3">
                        <p className="text-label-md text-on-surface-variant">
                          一键清空：清空记忆单元 + 记忆空间 + 实体 + 事件 + 摘要 + 基础记忆 + Neo4j + Milvus
                        </p>
                        <button
                          type="button"
                          disabled={clearing}
                          onClick={() =>
                            setClearTarget({
                              key: "all",
                              title: "清空所有数据",
                              message:
                                "将清空全部记忆数据（记忆单元、记忆空间、实体、事件、摘要、基础记忆、Neo4j、Milvus）。\n\n此操作不可恢复，请输入「确认」以继续。",
                              endpoint: "clear-everything",
                              danger: true,
                            })
                          }
                          className="px-4 py-2 rounded-lg bg-error text-white text-body-md font-bold hover:opacity-90 transition-opacity flex items-center gap-2 disabled:opacity-50"
                        >
                          <Icon name="delete_forever" filled className="text-[18px]" />
                          清空所有数据
                        </button>
                      </div>
                    </>
                  );
                })()}
              </section>
            </>
          )}
        </div>
      </div>

      {/* ── 全局清空确认弹窗（需输入"确认"才能执行） ── */}
      <ConfirmDialog
        open={!!clearTarget}
        title={clearTarget?.title || ""}
        message={clearTarget?.message}
        variant={clearTarget?.danger ? "danger" : "default"}
        confirmLabel={clearing ? "执行中..." : "确认清空"}
        requireText="确认"
        onConfirm={handleConfirmClear}
        onCancel={() => !clearing && setClearTarget(null)}
      />

      {/* ── 操作结果提示 ── */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-[110] max-w-md">
          <div
            className={[
              "rounded-xl shadow-lg px-4 py-3 flex items-start gap-3 border",
              toast.kind === "success"
                ? "bg-success/10 border-success/30 text-success"
                : "bg-error/10 border-error/30 text-error",
            ].join(" ")}
          >
            <Icon
              name={toast.kind === "success" ? "check_circle" : "error"}
              filled
              className="text-[20px] flex-shrink-0 mt-0.5"
            />
            <p className="text-body-md font-medium whitespace-pre-line">{toast.text}</p>
          </div>
        </div>
      )}
    </AppShell>
  );
}
