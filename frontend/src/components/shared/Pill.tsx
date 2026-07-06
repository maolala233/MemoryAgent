"use client";

interface PillProps {
  children: React.ReactNode;
  variant?: "default" | "primary" | "success" | "warning" | "error" | "info";
  size?: "sm" | "md";
  className?: string;
  onClick?: () => void;
}

const VARIANT_CLASSES: Record<NonNullable<PillProps["variant"]>, string> = {
  default: "bg-surface-container-low border-border text-on-secondary-container",
  primary: "bg-primary-fixed border-primary/20 text-primary",
  success: "bg-success/10 border-success/20 text-success",
  warning: "bg-warning/10 border-warning/20 text-warning",
  error: "bg-error/10 border-error/20 text-error",
  info: "bg-secondary-container border-border text-on-secondary-container",
};

const SIZE_CLASSES = {
  sm: "text-label-sm px-2 py-0.5",
  md: "text-label-md px-2.5 py-1",
};

export function Pill({
  children,
  variant = "default",
  size = "sm",
  className = "",
  onClick,
}: PillProps) {
  const Tag = onClick ? "button" : "span";
  return (
    <Tag
      onClick={onClick}
      className={[
        "inline-flex items-center gap-1 rounded-full border font-medium",
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        onClick ? "cursor-pointer hover:opacity-80 transition-opacity" : "",
        className,
      ].join(" ")}
    >
      {children}
    </Tag>
  );
}
