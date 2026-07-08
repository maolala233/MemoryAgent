"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Icon } from "@/components/shared/Icon";
import { Loading } from "@/components/shared/Loading";
import { Pill } from "@/components/shared/Pill";
import { EmptyState } from "@/components/shared/EmptyState";
import { useMemory } from "@/hooks/useMemory";
import type { MemoryDoc } from "@/types";

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function MemoryVaultPage() {
  return (
    <Suspense fallback={<Loading size="lg" label="Loading vault..." />}>
      <MemoryVaultContent />
    </Suspense>
  );
}

function MemoryVaultContent() {
  const searchParams = useSearchParams();
  const { data, isLoading, listDocuments } = useMemory();
  const [track, setTrack] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [hasOpenLoop, setHasOpenLoop] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const filter = searchParams.get("filter");
    if (filter === "open-loops") setHasOpenLoop(true);
  }, [searchParams]);

  useEffect(() => {
    listDocuments({
      track: track || undefined,
      memory_type: type || undefined,
      status: status || undefined,
      has_open_loop: hasOpenLoop || undefined,
      limit: 200,
    });
  }, [track, type, status, hasOpenLoop, listDocuments]);

  const filtered = useMemo(() => {
    if (!data?.items) return [];
    if (!search.trim()) return data.items;
    const q = search.toLowerCase();
    return data.items.filter(
      (m) =>
        (m.title || "").toLowerCase().includes(q) ||
        m.rel_path.toLowerCase().includes(q) ||
        (m.summary || "").toLowerCase().includes(q) ||
        m.keywords.some((k) => k.toLowerCase().includes(q)),
    );
  }, [data, search]);

  const tracks = useMemo(
    () => Array.from(new Set(data?.items.map((m) => m.track).filter(Boolean))),
    [data],
  );
  const types = useMemo(
    () => Array.from(new Set(data?.items.map((m) => m.memory_type).filter(Boolean))),
    [data],
  );

  const clearFilters = () => {
    setTrack("");
    setType("");
    setStatus("");
    setHasOpenLoop(false);
    setSearch("");
  };

  return (
    <AppShell title="记忆库" subtitle={`${data?.total ?? 0} documents`}>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="w-full px-panel-padding py-8 space-y-6">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[240px]">
              <Icon
                name="search"
                className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant"
              />
              <input
                type="text"
                placeholder="Filter memories..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none text-body-md"
              />
            </div>
            <select
              value={track}
              onChange={(e) => setTrack(e.target.value)}
              className="px-3 py-2 bg-surface border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
            >
              <option value="">All tracks</option>
              {tracks.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="px-3 py-2 bg-surface border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
            >
              <option value="">All types</option>
              {types.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="px-3 py-2 bg-surface border border-border rounded-lg text-body-md focus:ring-2 focus:ring-primary outline-none"
            >
              <option value="">Any status</option>
              <option value="active">Active</option>
              <option value="verified">Verified</option>
              <option value="archived">Archived</option>
              <option value="draft">Draft</option>
            </select>
            <label className="flex items-center gap-2 text-body-md text-on-surface-variant cursor-pointer">
              <input
                type="checkbox"
                checked={hasOpenLoop}
                onChange={(e) => setHasOpenLoop(e.target.checked)}
                className="rounded border-border"
              />
              Open loops only
            </label>
            {(track || type || status || hasOpenLoop || search) && (
              <button
                onClick={clearFilters}
                className="text-label-md text-on-surface-variant hover:text-error transition-colors flex items-center gap-1"
              >
                <Icon name="close" className="text-[14px]" />
                Clear
              </button>
            )}
            <Link
              href="/memory/new"
              className="ml-auto flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-md hover:opacity-90 transition-opacity"
            >
              <Icon name="add" className="text-[18px]" />
              New Entry
            </Link>
          </div>

          {/* List */}
          {isLoading && !data && <Loading label="Loading memories..." />}

          {data && filtered.length === 0 && (
            <EmptyState
              icon="inventory_2"
              title="No memories found"
              description="Try adjusting your filters, or create a new memory entry."
              action={
                <Link
                  href="/memory/new"
                  className="px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-md"
                >
                  + New Entry
                </Link>
              }
            />
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filtered.map((m: MemoryDoc) => (
              <Link
                key={m.rel_path}
                href={`/memory/${encodeURIComponent(m.rel_path)}`}
                className="block bg-surface border border-border rounded-xl p-4 hover:border-primary transition-colors group"
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Icon
                      name="description"
                      className="text-on-surface-variant group-hover:text-primary text-[20px] flex-shrink-0"
                    />
                    <h3 className="text-body-md font-bold text-on-surface truncate">
                      {m.title || m.rel_path}
                    </h3>
                  </div>
                  {m.open_loops.length > 0 && (
                    <Pill variant="warning" size="sm">
                      <Icon name="pending" className="text-[12px]" />
                      {m.open_loops.length}
                    </Pill>
                  )}
                </div>
                <p className="text-body-sm text-on-surface-variant mb-3 line-clamp-2">
                  {m.summary || m.content.slice(0, 140) + "..." || "No summary."}
                </p>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Pill variant="info" size="sm">
                    {m.track}
                  </Pill>
                  <Pill size="sm">{m.memory_type}</Pill>
                  <Pill variant={m.status === "verified" ? "success" : "default"} size="sm">
                    {m.status}
                  </Pill>
                  {m.keywords.slice(0, 3).map((k) => (
                    <Pill key={k} variant="primary" size="sm">
                      #{k}
                    </Pill>
                  ))}
                  <span className="ml-auto text-label-sm text-outline">
                    {formatDate(m.updated_at || m.indexed_at)}
                  </span>
                </div>
                <p className="text-label-sm text-outline mt-2 font-mono truncate">
                  {m.rel_path}
                </p>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
