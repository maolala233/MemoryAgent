"use client";

import { useCallback, useEffect, useState } from "react";

export function useLocalStorage<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(initial);
  const [isHydrated, setIsHydrated] = useState(false);

  // Read from localStorage after mount to avoid hydration mismatch
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(key);
      if (raw !== null) {
        setValue(JSON.parse(raw) as T);
      }
    } catch {
      // ignore
    }
    setIsHydrated(true);
  }, [key]);

  // Listen for storage events from other tabs / components
  useEffect(() => {
    if (!isHydrated) return;
    const handler = (e: StorageEvent) => {
      if (e.key === key && e.newValue !== null) {
        try {
          setValue(JSON.parse(e.newValue) as T);
        } catch {
          // ignore
        }
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, [key, isHydrated]);

  const set = useCallback(
    (next: T | ((prev: T) => T)) => {
      setValue((prev) => {
        const resolved = typeof next === "function" ? (next as (p: T) => T)(prev) : next;
        if (typeof window !== "undefined") {
          window.localStorage.setItem(key, JSON.stringify(resolved));
          // Dispatch a custom event for same-tab sync
          window.dispatchEvent(
            new StorageEvent("storage", {
              key,
              newValue: JSON.stringify(resolved),
            }),
          );
        }
        return resolved;
      });
    },
    [key],
  );

  const remove = useCallback(() => {
    if (typeof window !== "undefined") window.localStorage.removeItem(key);
    setValue(initial);
  }, [key, initial]);

  return [value, set, remove] as const;
}
