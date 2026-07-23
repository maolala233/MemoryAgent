"use client";

import { Icon } from "./Icon";

export interface PaginationProps {
  /** 当前页码，从 1 开始 */
  page: number;
  /** 每页条数 */
  pageSize: number;
  /** 数据总条数（来自后端的 total） */
  total: number;
  /** 切换页码时回调 */
  onPageChange: (page: number) => void;
  /** 切换每页大小时回调（通常会同时把 page 重置到 1） */
  onPageSizeChange: (size: number) => void;
  /** 可选的每页大小候选，默认 [10, 20, 50, 100] */
  pageSizeOptions?: number[];
  /** className 透传 */
  className?: string;
}

/**
 * 通用分页组件：
 * - 左侧: 每页大小选择 (10/20/50/100)
 * - 右侧: 「共 N 条 / 第 X / Y 页」+ 上一页 / 下一页 / 跳转
 *
 * 行为约定:
 * - total=0 时隐藏分页器, 仍显示每页大小选择 (不隐藏, 保持布局稳定).
 * - page 越界时, 上层应在收到 onPageChange 时重置.
 */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
  className = "",
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const end = Math.min(total, safePage * pageSize);

  return (
    <div
      className={[
        "flex flex-wrap items-center justify-between gap-3",
        "text-body-sm text-on-surface-variant",
        className,
      ].join(" ")}
    >
      {/* 左侧: 每页大小 */}
      <div className="flex items-center gap-2">
        <span className="text-label-md whitespace-nowrap">每页</span>
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="px-2 py-1 bg-surface border border-border rounded-md text-body-sm focus:ring-2 focus:ring-primary outline-none"
        >
          {pageSizeOptions.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        <span className="text-label-md whitespace-nowrap">条</span>
        <span className="ml-3 text-label-md whitespace-nowrap tabular-nums">
          共 <span className="text-on-surface font-medium">{total}</span> 条
          {total > 0 && (
            <>
              {" "}· 第 <span className="text-on-surface font-medium">{start}-{end}</span> 条
            </>
          )}
        </span>
      </div>

      {/* 右侧: 翻页控件 */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(1)}
          disabled={safePage <= 1}
          className="p-1.5 rounded-md hover:bg-surface-container disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="第一页"
          aria-label="第一页"
        >
          <Icon name="first_page" className="text-[20px]" />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(safePage - 1)}
          disabled={safePage <= 1}
          className="p-1.5 rounded-md hover:bg-surface-container disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="上一页"
          aria-label="上一页"
        >
          <Icon name="chevron_left" className="text-[20px]" />
        </button>
        <span className="px-3 py-1 text-label-md whitespace-nowrap tabular-nums">
          第 <span className="text-on-surface font-medium">{safePage}</span> / {totalPages} 页
        </span>
        <button
          type="button"
          onClick={() => onPageChange(safePage + 1)}
          disabled={safePage >= totalPages}
          className="p-1.5 rounded-md hover:bg-surface-container disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="下一页"
          aria-label="下一页"
        >
          <Icon name="chevron_right" className="text-[20px]" />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(totalPages)}
          disabled={safePage >= totalPages}
          className="p-1.5 rounded-md hover:bg-surface-container disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="最后一页"
          aria-label="最后一页"
        >
          <Icon name="last_page" className="text-[20px]" />
        </button>
      </div>
    </div>
  );
}
