"use client";

import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { useStats } from "@/hooks/useStats";

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function StatCard({
  icon,
  label,
  value,
  trend,
  variant = "default",
}: {
  icon: string;
  label: string;
  value: string | number;
  trend?: string;
  variant?: "default" | "primary" | "warning" | "error";
}) {
  const accent = {
    default: "bg-surface-container text-on-surface-variant",
    primary: "bg-primary-fixed text-primary",
    warning: "bg-warning/10 text-warning",
    error: "bg-error/10 text-error",
  }[variant];
  return (
    <div className="bg-surface border border-border rounded-xl p-5 hover:border-primary/40 transition-colors">
      <div className="flex items-start justify-between mb-4">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${accent}`}>
          <Icon name={icon} filled className="text-[22px]" />
        </div>
        {trend && (
          <Pill variant="success" size="sm">
            <Icon name="trending_up" className="text-[12px]" />
            {trend}
          </Pill>
        )}
      </div>
      <p className="text-headline-lg font-headline-lg font-bold text-on-surface">
        {value}
      </p>
      <p className="text-body-sm text-on-surface-variant mt-1">{label}</p>
    </div>
  );
}

function DistributionBar({
  label,
  count,
  total,
  color = "bg-primary",
}: {
  label: string;
  count: number;
  total: number;
  color?: string;
}) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-body-md text-on-surface font-medium">{label}</span>
        <span className="text-label-md text-on-surface-variant">
          {count} · {pct}%
        </span>
      </div>
      <div className="h-2 bg-surface-container rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

const TRACK_COLORS: Record<string, string> = {
  project: "bg-primary",
  learning: "bg-success",
  research: "bg-warning",
  reference: "bg-secondary",
  personal: "bg-error",
};

export default function DashboardPage() {
  const { overview, distribution, timeline, openLoops, recent, isLoading, error } = useStats();

  const totalByTrack = distribution
    ? Object.values(distribution.by_track).reduce((a, b) => a + b, 0)
    : 0;
  const totalByType = distribution
    ? Object.values(distribution.by_type).reduce((a, b) => a + b, 0)
    : 0;

  const maxTimeline = Math.max(1, ...timeline.map((p) => p.doc_count));

  return (
    <AppShell title="Dashboard" subtitle="Memory Vault Overview">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-max-content-width mx-auto px-panel-padding py-8 space-y-8">
          {error && (
            <div className="bg-error/10 border border-error/20 text-error rounded-lg p-4 flex items-center gap-2">
              <Icon name="error" filled />
              <span className="text-body-md">{error}</span>
            </div>
          )}

          {isLoading && !overview && <Loading size="lg" label="Loading dashboard..." />}

          {/* Stat cards */}
          {overview && (
            <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                icon="description"
                label="Total Memories"
                value={overview.total_docs}
                trend="+12%"
                variant="primary"
              />
              <StatCard
                icon="database"
                label="Vault Size"
                value={formatBytes(overview.total_size)}
              />
              <StatCard
                icon="pending_actions"
                label="Open Loops"
                value={overview.open_loops_count}
                variant={overview.open_loops_count > 0 ? "warning" : "default"}
              />
              <StatCard
                icon="update"
                label="Last Updated"
                value={formatDate(overview.last_updated)}
              />
            </section>
          )}

          {/* Distribution + Timeline */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* By Track */}
            <div className="bg-surface border border-border rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-body-lg font-bold text-on-surface">
                  Distribution by Track
                </h3>
                <Icon name="donut_large" className="text-on-surface-variant" />
              </div>
              <div className="space-y-3">
                {distribution &&
                  Object.entries(distribution.by_track).map(([track, count]) => (
                    <DistributionBar
                      key={track}
                      label={track}
                      count={count}
                      total={totalByTrack}
                      color={TRACK_COLORS[track] || "bg-primary"}
                    />
                  ))}
                {distribution && totalByTrack === 0 && (
                  <p className="text-body-sm text-on-surface-variant py-4 text-center">
                    No memories yet.
                  </p>
                )}
              </div>
            </div>

            {/* By Type */}
            <div className="bg-surface border border-border rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-body-lg font-bold text-on-surface">
                  Distribution by Type
                </h3>
                <Icon name="category" className="text-on-surface-variant" />
              </div>
              <div className="space-y-3">
                {distribution &&
                  Object.entries(distribution.by_type).map(([type, count]) => (
                    <DistributionBar
                      key={type}
                      label={type}
                      count={count}
                      total={totalByType}
                      color="bg-success"
                    />
                  ))}
                {distribution && totalByType === 0 && (
                  <p className="text-body-sm text-on-surface-variant py-4 text-center">
                    No memories yet.
                  </p>
                )}
              </div>
            </div>

            {/* Timeline */}
            <div className="bg-surface border border-border rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-body-lg font-bold text-on-surface">
                  Activity (30d)
                </h3>
                <Icon name="timeline" className="text-on-surface-variant" />
              </div>
              <div className="flex items-end justify-between gap-0.5 h-32">
                {timeline.length === 0 && (
                  <p className="text-body-sm text-on-surface-variant m-auto">
                    No activity recorded.
                  </p>
                )}
                {timeline.map((p, i) => (
                  <div
                    key={i}
                    className="flex-1 bg-primary/70 hover:bg-primary rounded-t transition-colors"
                    style={{
                      height: `${(p.doc_count / maxTimeline) * 100}%`,
                      minHeight: p.doc_count > 0 ? "4px" : "0",
                    }}
                    title={`${p.date}: ${p.doc_count} new`}
                  />
                ))}
              </div>
              <p className="text-label-sm text-on-surface-variant mt-3 text-center">
                {timeline.length > 0 && (
                  <>
                    {timeline[0].date} → {timeline[timeline.length - 1].date}
                  </>
                )}
              </p>
            </div>
          </section>

          {/* Recent + Open Loops */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Recent memories */}
            <div className="bg-surface border border-border rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-body-lg font-bold text-on-surface">Recent Memories</h3>
                <Link
                  href="/memory"
                  className="text-label-md text-primary hover:underline flex items-center gap-1"
                >
                  View all <Icon name="arrow_forward" className="text-[14px]" />
                </Link>
              </div>
              <div className="space-y-2">
                {recent?.items.map((m) => (
                  <Link
                    key={m.rel_path}
                    href={`/memory/${encodeURIComponent(m.rel_path)}`}
                    className="block p-3 rounded-lg hover:bg-surface-container-low transition-colors group"
                  >
                    <div className="flex items-start gap-3">
                      <Icon
                        name="description"
                        className="text-on-surface-variant group-hover:text-primary text-[20px] mt-0.5"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-body-md font-medium text-on-surface truncate">
                          {m.title || m.rel_path}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <Pill variant="info" size="sm">
                            {m.track}
                          </Pill>
                          <Pill size="sm">{m.memory_type}</Pill>
                          <span className="text-label-sm text-outline ml-auto">
                            {formatDate(m.updated_at || m.indexed_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
                {recent && recent.items.length === 0 && (
                  <EmptyState
                    icon="inbox"
                    title="No memories yet"
                    description="Import a document or create a new entry to populate your vault."
                    action={
                      <Link
                        href="/import"
                        className="text-body-md text-primary hover:underline"
                      >
                        Import Document →
                      </Link>
                    }
                  />
                )}
              </div>
            </div>

            {/* Open loops */}
            <div className="bg-surface border border-border rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-body-lg font-bold text-on-surface">Open Loops</h3>
                <Link
                  href="/memory?filter=open-loops"
                  className="text-label-md text-primary hover:underline flex items-center gap-1"
                >
                  Resolve <Icon name="arrow_forward" className="text-[14px]" />
                </Link>
              </div>
              <div className="space-y-2">
                {openLoops.map((loop, i) => (
                  <Link
                    key={i}
                    href={`/memory/${encodeURIComponent(loop.path)}`}
                    className="block p-3 rounded-lg hover:bg-surface-container-low transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <Icon
                        name={
                          loop.priority === "high"
                            ? "priority_high"
                            : "radio_button_unchecked"
                        }
                        filled={loop.priority === "high"}
                        className={`text-[20px] mt-0.5 ${
                          loop.priority === "high" ? "text-error" : "text-on-surface-variant"
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-body-md text-on-surface">{loop.item}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Pill variant="warning" size="sm">
                            {loop.kind}
                          </Pill>
                          <span className="text-label-sm text-outline truncate">
                            {loop.title}
                          </span>
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
                {openLoops.length === 0 && (
                  <EmptyState
                    icon="check_circle"
                    title="All clear"
                    description="No open loops detected in your memory vault."
                  />
                )}
              </div>
            </div>
          </section>

          {/* Quick actions */}
          <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link
              href="/search"
              className="bg-surface border border-border rounded-xl p-5 hover:border-primary transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary-fixed text-primary flex items-center justify-center">
                  <Icon name="search" filled />
                </div>
                <div>
                  <p className="text-body-md font-bold text-on-surface">Global Search</p>
                  <p className="text-body-sm text-on-surface-variant">
                    Hybrid keyword + semantic
                  </p>
                </div>
                <Icon
                  name="arrow_forward"
                  className="ml-auto text-on-surface-variant group-hover:text-primary"
                />
              </div>
            </Link>
            <Link
              href="/chat"
              className="bg-surface border border-border rounded-xl p-5 hover:border-primary transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary-fixed text-primary flex items-center justify-center">
                  <Icon name="smart_toy" filled />
                </div>
                <div>
                  <p className="text-body-md font-bold text-on-surface">Chat with Agent</p>
                  <p className="text-body-sm text-on-surface-variant">
                    Retrieval-augmented dialogue
                  </p>
                </div>
                <Icon
                  name="arrow_forward"
                  className="ml-auto text-on-surface-variant group-hover:text-primary"
                />
              </div>
            </Link>
            <Link
              href="/import"
              className="bg-surface border border-border rounded-xl p-5 hover:border-primary transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary-fixed text-primary flex items-center justify-center">
                  <Icon name="upload_file" filled />
                </div>
                <div>
                  <p className="text-body-md font-bold text-on-surface">Import Document</p>
                  <p className="text-body-sm text-on-surface-variant">
                    PDF / DOCX / MD → Memory
                  </p>
                </div>
                <Icon
                  name="arrow_forward"
                  className="ml-auto text-on-surface-variant group-hover:text-primary"
                />
              </div>
            </Link>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
