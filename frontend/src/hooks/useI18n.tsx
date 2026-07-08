"use client";

import { ReactNode } from "react";

// 简化的 i18n 上下文：纯中文模式，t() 直接返回 key 作为兜底。
// 保留此 Provider 以兼容现有使用 useI18n 的组件。
const I18nContext = {
  locale: "zh" as const,
  t: (key: string) => key,
  setLocale: () => {},
  toggleLocale: () => {},
};

export function I18nProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function useI18n() {
  return I18nContext;
}
