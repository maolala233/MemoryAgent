"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { Icon } from "@/components/shared/Icon";

interface TopBarProps {
  title?: string;
  subtitle?: string;
  showSearch?: boolean;
  rightSlot?: React.ReactNode;
}

export function TopBar({
  title,
  subtitle,
  showSearch = true,
  rightSlot,
}: TopBarProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");

  // ⌘K / Ctrl+K shortcut to focus search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        const input = document.getElementById("topbar-search");
        (input as HTMLInputElement | null)?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  };

  return (
    <header className="fixed top-0 right-0 left-[220px] h-touch-target bg-surface border-b border-border flex items-center justify-between px-panel-padding z-40">
      <div className="flex items-center gap-4 min-w-0">
        {title && (
          <div className="flex items-center gap-2 min-w-0">
            <h2 className="text-body-lg font-bold text-on-surface truncate">
              {title}
            </h2>
            {subtitle && (
              <>
                <div className="h-4 w-px bg-border" />
                <span className="text-label-md text-on-surface-variant truncate">
                  {subtitle}
                </span>
              </>
            )}
          </div>
        )}
        
      </div>

      <div className="flex items-center gap-2">
        {rightSlot}
      </div>
    </header>
  );
}
