import { useState, useEffect, useCallback } from "react";

export type ReaderTheme = "light" | "dark" | "sepia";
export type ColumnWidth = "narrow" | "normal" | "wide";

export interface ReaderPrefs {
  fontSize: number;          // px, 12–22
  columnWidth: ColumnWidth;
  theme: ReaderTheme;
}

const DEFAULTS: ReaderPrefs = {
  fontSize: 16,
  columnWidth: "normal",
  theme: (localStorage.getItem("theme") as ReaderTheme) || "dark",
};

const STORAGE_KEY = "kiwi-reader-prefs";

function loadPrefs(): ReaderPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<ReaderPrefs>;
    return {
      fontSize: Math.min(22, Math.max(12, parsed.fontSize ?? DEFAULTS.fontSize)),
      columnWidth: parsed.columnWidth ?? DEFAULTS.columnWidth,
      theme: parsed.theme ?? DEFAULTS.theme,
    };
  } catch {
    return DEFAULTS;
  }
}

/**
 * Shared reader preferences hook.
 * Persists to localStorage and emits a custom DOM event so other listeners
 * (e.g. the article-iframe parent) can react to changes without prop drilling.
 */
export function useReaderPrefs() {
  const [prefs, setPrefs] = useState<ReaderPrefs>(loadPrefs);

  // Persist + broadcast
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    window.dispatchEvent(new CustomEvent("kiwi-prefs-changed", { detail: prefs }));
  }, [prefs]);

  // Allow components mounted before us to subscribe
  useEffect(() => {
    const handler = (e: Event) => {
      const next = (e as CustomEvent<ReaderPrefs>).detail;
      setPrefs(p => (JSON.stringify(p) === JSON.stringify(next) ? p : next));
    };
    window.addEventListener("kiwi-prefs-changed", handler);
    return () => window.removeEventListener("kiwi-prefs-changed", handler);
  }, []);

  const setFontSize = useCallback(
    (v: number) => setPrefs(p => ({ ...p, fontSize: Math.min(22, Math.max(12, v)) })),
    []
  );
  const setColumnWidth = useCallback(
    (v: ColumnWidth) => setPrefs(p => ({ ...p, columnWidth: v })),
    []
  );
  const setTheme = useCallback(
    (v: ReaderTheme) => setPrefs(p => ({ ...p, theme: v })),
    []
  );

  return { prefs, setFontSize, setColumnWidth, setTheme };
}
