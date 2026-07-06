"use client";

import { Icon } from "./Icon";

interface LoadingProps {
  size?: "sm" | "md" | "lg";
  label?: string;
}

export function Loading({ size = "md", label }: LoadingProps) {
  const sizeClass = {
    sm: "text-[16px]",
    md: "text-[24px]",
    lg: "text-[40px]",
  }[size];

  return (
    <div className="flex items-center justify-center gap-3 py-8 text-on-surface-variant">
      <Icon
        name="progress_activity"
        className={`${sizeClass} animate-spin`}
      />
      {label && <span className="text-body-md">{label}</span>}
    </div>
  );
}
