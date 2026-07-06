"use client";

import { useEffect } from "react";
import { Icon } from "./Icon";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div
        className="absolute inset-0 bg-on-surface/40 backdrop-blur-sm"
        onClick={onCancel}
      />
      <div className="relative bg-surface border border-border rounded-xl shadow-lg w-full max-w-md mx-4 p-6">
        <div className="flex items-start gap-3 mb-2">
          <div
            className={[
              "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
              variant === "danger"
                ? "bg-error/10 text-error"
                : "bg-primary-fixed text-primary",
            ].join(" ")}
          >
            <Icon
              name={variant === "danger" ? "warning" : "help"}
              filled
              className="text-[20px]"
            />
          </div>
          <h3 className="text-body-lg font-bold text-on-surface mt-1">
            {title}
          </h3>
        </div>
        {message && (
          <p className="text-body-md text-on-surface-variant mb-6 pl-11">
            {message}
          </p>
        )}
        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-body-md font-medium text-on-surface-variant hover:bg-surface-container-low rounded-lg transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={[
              "px-4 py-2 text-body-md font-bold text-white rounded-lg transition-opacity hover:opacity-90",
              variant === "danger" ? "bg-error" : "bg-primary",
            ].join(" ")}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
