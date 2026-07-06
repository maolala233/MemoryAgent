"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/shared/Icon";

interface NavItem {
  label: string;
  href: string;
  icon: string;
  filledIcon?: string;
}

const PRIMARY_NAV: NavItem[] = [
  { label: "Dashboard", href: "/", icon: "dashboard" },
  { label: "Memory Vault", href: "/memory", icon: "inventory_2" },
  { label: "Search", href: "/search", icon: "search" },
  { label: "Chat with Agent", href: "/chat", icon: "smart_toy" },
  { label: "Import Document", href: "/import", icon: "upload_file" },
  { label: "Agents", href: "/agents", icon: "neurology" },
];

const FOOTER_NAV: NavItem[] = [
  { label: "Settings", href: "/settings", icon: "settings" },
  { label: "Support", href: "/support", icon: "help" },
];

export function Sidebar() {
  const pathname = usePathname();

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
          "flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 cursor-pointer active:scale-95",
          active
            ? "bg-primary-fixed-dim text-on-primary-fixed-variant font-bold"
            : "text-on-surface-variant hover:bg-surface-container-low",
        ].join(" ")}
      >
        <Icon name={item.icon} filled={active} className="text-[20px]" />
        <span className="font-body-md">{item.label}</span>
      </Link>
    );
  };

  return (
    <aside className="fixed left-0 top-0 h-full w-[280px] bg-surface border-r border-border flex flex-col p-panel-padding z-50">
      {/* Brand */}
      <div className="mb-8 px-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary rounded flex items-center justify-center">
            <Icon name="terminal" filled className="text-white text-[20px]" />
          </div>
          <div>
            <h1 className="text-headline-sm font-headline-sm font-bold text-primary">
              Codex Memory
            </h1>
            <p className="text-label-sm text-on-surface-variant flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-success rounded-full"></span>
              Agent: Online
            </p>
          </div>
        </div>
      </div>

      {/* Primary nav */}
      <nav className="flex-1 space-y-1">{PRIMARY_NAV.map(renderLink)}</nav>

      {/* New Entry button */}
      <Link
        href="/memory/new"
        className="mt-4 w-full bg-primary text-on-primary py-2.5 rounded-lg font-bold text-body-md hover:bg-opacity-90 transition-all flex items-center justify-center gap-2 mb-8 active:scale-95"
      >
        <Icon name="add" className="text-[20px]" />
        New Entry
      </Link>

      {/* Footer nav */}
      <div className="border-t border-border pt-4 space-y-1">
        {FOOTER_NAV.map(renderLink)}
      </div>
    </aside>
  );
}
