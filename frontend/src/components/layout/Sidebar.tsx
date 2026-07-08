"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/shared/Icon";

interface NavItem {
  label: string;
  href: string;
  icon: string;
}

export function Sidebar() {
  const pathname = usePathname();

  const PRIMARY_NAV: NavItem[] = [
    { label: "仪表盘", href: "/", icon: "dashboard" },
    { label: "记忆库", href: "/memory", icon: "inventory_2" },
    { label: "记忆检索", href: "/search", icon: "search" },
    { label: "智能问答", href: "/chat", icon: "smart_toy" },
    { label: "记忆单元", href: "/units", icon: "memory" },
    { label: "记忆空间", href: "/spaces", icon: "workspaces" },
    { label: "知识图谱", href: "/graph", icon: "account_tree" },
    { label: "记忆构建", href: "/build", icon: "construction" },
    { label: "文档导入", href: "/import", icon: "upload_file" },
    { label: "Agent", href: "/agents", icon: "neurology" },
  ];

  const FOOTER_NAV: NavItem[] = [
    { label: "系统设置", href: "/settings", icon: "settings" },
  ];

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname?.startsWith(href);
  };

  const renderLink = (item: NavItem) => {
    const active = isActive(item.href);
    return (
      <Link
        key={item.href}
        href={item.href}
        className={[
          "flex items-center gap-2.5 px-3 py-1.5 rounded-lg transition-all duration-200 cursor-pointer active:scale-95",
          active
            ? "bg-primary-fixed-dim text-on-primary-fixed-variant font-bold"
            : "text-on-surface-variant hover:bg-surface-container-low",
        ].join(" ")}
      >
        <Icon name={item.icon} filled={active} className="text-[18px]" />
        <span className="text-body-md">{item.label}</span>
      </Link>
    );
  };

  return (
    <aside className="fixed left-0 top-0 h-full w-[220px] bg-surface border-r border-border flex flex-col px-4 py-5 z-50">
      {/* 品牌 */}
      <div className="mb-5 px-2">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-primary rounded flex items-center justify-center flex-shrink-0">
            <Icon name="terminal" filled className="text-white text-[18px]" />
          </div>
          <div className="min-w-0">
            <h1 className="text-body-lg font-bold text-primary leading-tight">
              记忆问答平台
            </h1>
            <p className="text-label-sm text-on-surface-variant flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-success rounded-full"></span>
              基于 Mandol的问答引擎
            </p>
          </div>
        </div>
      </div>

      {/* 主导航 */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto custom-scrollbar">
        {PRIMARY_NAV.map(renderLink)}
      </nav>

      {/* 新建入口 */}
      <Link
        href="/memory/new"
        className="mt-3 w-full bg-primary text-on-primary py-2 rounded-lg font-bold text-body-md hover:bg-opacity-90 transition-all flex items-center justify-center gap-2 mb-3 active:scale-95"
      >
        <Icon name="add" className="text-[18px]" />
        新建记忆
      </Link>

      {/* 底部导航 */}
      <div className="border-t border-border pt-3 space-y-0.5">
        {FOOTER_NAV.map(renderLink)}
      </div>
    </aside>
  );
}
