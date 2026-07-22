"use client";

import { useEffect, useState } from "react";
import { Icon } from "./Icon";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "danger";
  /** 需要用户在输入框中输入的字符串（留空则不需要） */
  requireText?: string;
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
  requireText,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (open) setTyped("");
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onCancel]);

  if (!open) return null;

  const textMatched = !requireText || typed === requireText;

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
          <p className="text-body-md text-on-surface-variant mb-4 pl-11 whitespace-pre-line">
            {message}
          </p>
        )}
        {requireText && (
          <div className="pl-11 mb-2">
            <label className="block text-label-md text-on-surface-variant mb-1">
              请输入 <code className="px-1 py-0.5 rounded bg-surface-container-high text-on-surface font-mono">{requireText}</code> 以确认操作
            </label>
            <input
              type="text"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-container-low text-body-md focus:outline-none focus:border-primary"
              autoFocus
            />
          </div>
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
            disabled={!textMatched}
            className={[
              "px-4 py-2 text-body-md font-bold text-white rounded-lg transition-opacity",
              textMatched ? "hover:opacity-90" : "opacity-40 cursor-not-allowed",
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
