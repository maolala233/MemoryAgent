"use client";

/**
 * 关键词 → 单元 模糊搜索下拉（小白友好入口）：
 *  - 调 /api/mandol/units?q=xxx
 *  - 选中后回填 uid（也保留 display text 给用户看）
 *  - 支持 debounce、loading、空态、清除
 */

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/shared/Icon";

export interface UnitHit {
  uid: string;
  text?: string;
  space_name?: string;
  metadata?: Record<string, unknown>;
}

interface EntitySearchInputProps {
  /** 当前已选中的 uid（受控） */
  value: string;
  onChange: (uid: string, hit?: UnitHit) => void;
  placeholder?: string;
  /** 限定空间（可选） */
  spaceName?: string;
  /** 输入框左侧标签 */
  label?: string;
  /** 是否禁用 */
  disabled?: boolean;
  className?: string;
}

const TRUNCATE = (s: string | undefined, n: number): string => {
  if (!s) return "";
  return s.length > n ? s.slice(0, n) + "…" : s;
};

export function EntitySearchInput({
  value,
  onChange,
  placeholder = "输入关键词搜索记忆单元",
  spaceName,
  label = "中心节点",
  disabled,
  className,
}: EntitySearchInputProps) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<UnitHit[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [selectedLabel, setSelectedLabel] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reqIdRef = useRef(0);

  // 外部 value 变化时同步 label（用于显示"已选中: XXX"）
  useEffect(() => {
    if (!value) {
      setSelectedLabel("");
      return;
    }
    // 简化：直接展示 uid 短哈希
    setSelectedLabel((prev) => {
      if (prev && prev.startsWith("✓ ")) return prev;
      return `✓ 已锁定: ${TRUNCATE(value, 36)}`;
    });
  }, [value]);

  // 点击外部关闭下拉
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (!wrapRef.current) return;
      if (!wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const doSearch = async (kw: string) => {
    if (!kw.trim()) {
      setHits([]);
      setLoading(false);
      return;
    }
    const myReqId = ++reqIdRef.current;
    setLoading(true);
    setErr(null);
    try {
      const params = new URLSearchParams({ q: kw, limit: "12" });
      if (spaceName) params.set("space", spaceName);
      const resp = await fetch(`/api/mandol/units?${params.toString()}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (myReqId !== reqIdRef.current) return;  // 过期
      const items: UnitHit[] = (data.items || []).map((it: UnitHit) => ({
        uid: it.uid,
        text: it.text,
        space_name: it.space_name,
        metadata: it.metadata,
      }));
      setHits(items);
      setActiveIdx(items.length > 0 ? 0 : -1);
      setOpen(true);
    } catch (e) {
      if (myReqId !== reqIdRef.current) return;
      setErr(e instanceof Error ? e.message : String(e));
      setHits([]);
    } finally {
      if (myReqId === reqIdRef.current) setLoading(false);
    }
  };

  const onInputChange = (v: string) => {
    setQuery(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(v), 300);
  };

  const pick = (hit: UnitHit) => {
    onChange(hit.uid, hit);
    setSelectedLabel(`✓ ${TRUNCATE(hit.text || hit.uid, 56)}`);
    setOpen(false);
    setQuery("");
  };

  const clear = () => {
    onChange("", undefined);
    setSelectedLabel("");
    setQuery("");
    setHits([]);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || hits.length === 0) {
      if (e.key === "ArrowDown" && query) doSearch(query);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(hits.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const hit = hits[activeIdx];
      if (hit) pick(hit);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={wrapRef} className={`relative ${className || ""}`}>
      {label && (
        <label className="block text-label-md text-on-surface-variant mb-1">{label}</label>
      )}
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant pointer-events-none">
          <Icon name="search" className="text-[18px]" />
        </span>
        <input
          type="text"
          value={query}
          disabled={disabled}
          onChange={(e) => onInputChange(e.target.value)}
          onFocus={() => {
            if (query) doSearch(query);
          }}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          className="w-full pl-9 pr-24 py-2 rounded-lg border border-border bg-surface text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {loading && (
            <Icon name="progress_activity" className="text-[16px] text-on-surface-variant animate-spin" />
          )}
          {(query || value) && (
            <button
              type="button"
              onClick={clear}
              className="w-6 h-6 rounded hover:bg-surface-container-low text-on-surface-variant flex items-center justify-center"
              title="清空"
            >
              <Icon name="close" className="text-[14px]" />
            </button>
          )}
        </div>
      </div>
      {/* 已选展示 */}
      {selectedLabel && !open && (
        <div className="mt-1 text-label-sm text-on-surface-variant truncate">{selectedLabel}</div>
      )}
      {/* 错误 */}
      {err && <div className="mt-1 text-label-sm text-error">搜索失败: {err}</div>}
      {/* 下拉 */}
      {open && (
        <div className="absolute z-20 left-0 right-0 mt-1 bg-surface border border-border rounded-lg shadow-lg max-h-80 overflow-y-auto custom-scrollbar">
          {hits.length === 0 ? (
            <div className="px-3 py-3 text-body-sm text-on-surface-variant">
              {loading ? "搜索中…" : query ? "没有匹配的记忆单元" : "输入关键词开始搜索"}
            </div>
          ) : (
            hits.map((h, i) => (
              <button
                type="button"
                key={h.uid}
                onClick={() => pick(h)}
                onMouseEnter={() => setActiveIdx(i)}
                className={`w-full text-left px-3 py-2 border-b border-border last:border-0 ${
                  i === activeIdx ? "bg-primary/8" : "hover:bg-surface-container-low"
                }`}
              >
                <div className="text-body-sm text-on-surface line-clamp-2">
                  {TRUNCATE(h.text || h.uid, 120)}
                </div>
                <div className="text-label-sm text-on-surface-variant mt-0.5 flex items-center gap-2">
                  <Icon name="fingerprint" className="text-[12px]" />
                  <span className="font-mono">{TRUNCATE(h.uid, 48)}</span>
                  {h.space_name && (
                    <>
                      <Icon name="folder" className="text-[12px] ml-2" />
                      <span>{h.space_name}</span>
                    </>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
