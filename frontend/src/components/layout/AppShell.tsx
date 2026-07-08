"use client";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface AppShellProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  showSearch?: boolean;
  rightSlot?: React.ReactNode;
  noTopBar?: boolean;
}

export function AppShell({
  children,
  title,
  subtitle,
  showSearch = true,
  rightSlot,
  noTopBar = false,
}: AppShellProps) {
  return (
    <>
      <Sidebar />
      {!noTopBar && (
        <TopBar
          title={title}
          subtitle={subtitle}
          showSearch={showSearch}
          rightSlot={rightSlot}
        />
      )}
      <main
        className={[
          "ml-[160px] h-screen flex w-[calc(100%-220px)]",
          noTopBar ? "" : "pt-touch-target",
        ].join(" ")}
      >
        {children}
      </main>
    </>
  );
}
