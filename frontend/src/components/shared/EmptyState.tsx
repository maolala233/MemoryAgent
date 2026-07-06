"use client";

import { Icon } from "./Icon";

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({
  icon = "inbox",
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="w-14 h-14 rounded-full bg-surface-container flex items-center justify-center mb-4">
        <Icon name={icon} className="text-[28px] text-on-surface-variant" />
      </div>
      <h3 className="text-body-lg font-bold text-on-surface mb-1">{title}</h3>
      {description && (
        <p className="text-body-md text-on-surface-variant max-w-sm">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
