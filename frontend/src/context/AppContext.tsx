import {
  createContext, useContext, useState, useEffect, useCallback, useRef,
  type ReactNode,
} from "react";
import type { Archive, Category, Tab, TabHistoryEntry, Bookmark } from "../types";
import { api } from "../services/api";
import { useToast } from "../components/Toast";

interface AppContextValue {
  theme: string;
  toggleTheme: () => void;
  archives: Archive[];
  fetchArchives: () => Promise<void>;
  deleteArchive: (id: string) => Promise<void>;
  categories: Category[];
  fetchCategories: () => Promise<void>;
  activeCategory: Category | null;
  setActiveCategory: (cat: Category | null) => void;
  tabs: Tab[];
  activeTabId: string | null;
  setActiveTabId: (id: string | null) => void;
  openArticleInTab: (
    title: string,
    path: string,
    archiveId: string,
    opts?: { from?: TabHistoryEntry; replaceCurrent?: boolean }
  ) => void;
  closeTab: (tabId: string) => void;
  updateTab: (tabId: string, updates: Partial<Tab>) => void;
  bookmarks: Bookmark[];
  toggleBookmark: (title: string, path: string, archiveId: string) => void;
  recentlyViewed: Bookmark[];
  pushRecentlyViewed: (title: string, path: string, archiveId: string) => void;
  scanPath: string;
  setScanPath: (path: string) => void;
  isScanning: boolean;
  scanZimFolder: () => Promise<void>;
  pickAndScanDirectory: () => Promise<void>;
  pickAndAddFiles: () => Promise<void>;
  startIndexing: (archiveId: string) => Promise<void>;
  pauseIndexing: (archiveId: string) => Promise<void>;
  cancelIndexing: (archiveId: string) => Promise<void>;
  extractArchive: (archiveId: string) => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

interface Props {
  children: ReactNode;
  onNavigate?: (view: string) => void;
}

export function AppProvider({ children, onNavigate }: Props) {
  const { showToast } = useToast();

  // Theme
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");

  const toggleTheme = useCallback(() => {
    setTheme(prev => {
      const next = prev === "dark" ? "light" : "dark";
      localStorage.setItem("theme", next);
      document.body.className = next;
      return next;
    });
  }, []);

  useEffect(() => {
    document.body.className = theme;
  }, [theme]);

  // Archives
  const [archives, setArchives] = useState<Archive[]>([]);

  const fetchArchives = useCallback(async () => {
    try {
      const data = await api.getArchives();
      setArchives(data);
    } catch (err) {
      showToast(`Failed to load archives: ${err instanceof Error ? err.message : "Unknown error"}`, "error");
    }
  }, [showToast]);

  // Categories
  const [categories, setCategories] = useState<Category[]>([]);

  const fetchCategories = useCallback(async () => {
    try {
      const data = await api.getCategories();
      setCategories(data);
    } catch (err) {
      showToast(`Failed to load categories: ${err instanceof Error ? err.message : "Unknown error"}`, "error");
    }
  }, [showToast]);

  // Active category filter
  const [activeCategory, setActiveCategory] = useState<Category | null>(null);

  // Tabs are intentionally NOT restored from localStorage — the app always
  // opens to a clean search page with no tabs.  Tabs opened during the
  // session are still saved to localStorage as a soft backup but they no
  // longer auto-reload on launch.
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(() => {
    try { return localStorage.getItem("kiwi-active-tab"); } catch { return null; }
  });

  // Persist tabs on every change
  useEffect(() => {
    try { localStorage.setItem("kiwi-tabs", JSON.stringify(tabs)); }
    catch { /* quota etc — non-fatal */ }
  }, [tabs]);
  useEffect(() => {
    try {
      if (activeTabId) localStorage.setItem("kiwi-active-tab", activeTabId);
      else localStorage.removeItem("kiwi-active-tab");
    } catch { /* */ }
  }, [activeTabId]);

  // Recently viewed (last 20 articles, deduped by archiveId+path)
  const [recentlyViewed, setRecentlyViewed] = useState<Bookmark[]>(() => {
    try {
      const raw = localStorage.getItem("kiwi-recent");
      return raw ? (JSON.parse(raw) as Bookmark[]) : [];
    } catch { return []; }
  });

  const pushRecentlyViewed = useCallback(
    (title: string, path: string, archiveId: string) => {
      setRecentlyViewed(prev => {
        const filtered = prev.filter(
          b => !(b.path === path && b.archiveId === archiveId)
        );
        const next = [
          { id: `${archiveId}-${path}`, title, path, archiveId },
          ...filtered,
        ].slice(0, 20);
        try { localStorage.setItem("kiwi-recent", JSON.stringify(next)); } catch { /* non-fatal */ }
        return next;
      });
    },
    []
  );

  const openArticleInTab = useCallback((
    title: string,
    path: string,
    archiveId: string,
    opts?: { from?: TabHistoryEntry; replaceCurrent?: boolean }
  ) => {
    const tabId = `${archiveId}-${path}-${Date.now()}`;
    const current: TabHistoryEntry = { path, archiveId, title };
    // When opened from a link click inside another article we pre-populate the
    // history so the back arrow returns to the source article.
    const history: TabHistoryEntry[] = opts?.from
      ? [opts.from, current]
      : [current];
    const newTab: Tab = {
      id: tabId,
      title,
      path,
      archiveId,
      history,
      historyIndex: history.length - 1,
    };
    setTabs(prev => [...prev, newTab]);
    setActiveTabId(tabId);
    pushRecentlyViewed(title, path, archiveId);
    onNavigate?.("reader");
  }, [onNavigate, pushRecentlyViewed]);

  const updateTab = useCallback((tabId: string, updates: Partial<Tab>) => {
    setTabs(prev => prev.map(t => t.id === tabId ? { ...t, ...updates } : t));
  }, []);

  const closeTab = useCallback((tabId: string) => {
    setTabs(prev => prev.filter(t => t.id !== tabId));
  }, []);

  // Keep activeTabId consistent when tabs change
  const activeTabIdRef = useRef(activeTabId);
  useEffect(() => {
    activeTabIdRef.current = activeTabId;
  }, [activeTabId]);
  useEffect(() => {
    const stillExists = tabs.some(t => t.id === activeTabIdRef.current);
    if (!stillExists && tabs.length > 0) {
      setActiveTabId(tabs[tabs.length - 1].id);
    } else if (!stillExists) {
      setActiveTabId(null);
    }
  }, [tabs]);

  // Bookmarks
  const [bookmarks, setBookmarks] = useState<Bookmark[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("bookmarks") || "[]");
    } catch {
      return [];
    }
  });

  const toggleBookmark = useCallback((title: string, path: string, archiveId: string) => {
    setBookmarks(prev => {
      const exists = prev.some(b => b.path === path && b.archiveId === archiveId);
      let updated: Bookmark[];
      if (exists) {
        updated = prev.filter(b => !(b.path === path && b.archiveId === archiveId));
      } else {
        updated = [...prev, { id: `${archiveId}-${path}`, title, path, archiveId }];
      }
      localStorage.setItem("bookmarks", JSON.stringify(updated));
      return updated;
    });
  }, []);

  // Scan path
  const [scanPath, setScanPath] = useState(() => localStorage.getItem("scanPath") || "");
  const [isScanning, setIsScanning] = useState(false);

  const setScanPathPersisted = useCallback((path: string) => {
    setScanPath(path);
    localStorage.setItem("scanPath", path);
  }, []);

  const _doScan = useCallback(async (dir: string) => {
    const trimmed = dir.trim();
    if (!trimmed) {
      showToast("Enter a directory path first.", "error");
      return;
    }
    setScanPathPersisted(trimmed);
    try { await api.updateSettings({ zim_scan_path: trimmed }); } catch { /* non-critical — path persists locally anyway */ }

    setIsScanning(true);
    try {
      const data = await api.scanDirectory(trimmed);
      setArchives(data);

      const idle = data.filter(a => a.status === "idle");
      for (const archive of idle) {
        try { await api.startIndexing(archive.id); } catch { /* indexing failures surface via toast/status */ }
      }

      const msg = idle.length > 0
        ? `Found ${data.length} archive(s). Indexing ${idle.length} in background.`
        : `Found ${data.length} archive(s). All already indexed.`;
      showToast(msg, "success");
      onNavigate?.("archives");
    } catch (err) {
      showToast(`Scan failed: ${err instanceof Error ? err.message : "Unknown error"}`, "error");
    } finally {
      setIsScanning(false);
    }
  }, [onNavigate, showToast, setScanPathPersisted]);

  const scanZimFolder = useCallback(() => _doScan(scanPath), [_doScan, scanPath]);

  const pickAndScanDirectory = useCallback(async () => {
    if (window.electronAPI?.isElectron) {
      const dir = await window.electronAPI.selectDirectory();
      if (dir) await _doScan(dir);
    } else {
      await _doScan(scanPath);
    }
  }, [_doScan, scanPath]);

  const pickAndAddFiles = useCallback(async () => {
    const files = window.electronAPI?.isElectron
      ? await window.electronAPI.selectFiles?.()
      : null;
    if (!files || files.length === 0) return;
    setIsScanning(true);
    try {
      const data = await api.addFiles(files);
      if (data.length === 0) {
        showToast("No new archives were added.", "error");
        return;
      }
      setArchives(prev => {
        const existingIds = new Set(prev.map(a => a.id));
        return [...prev, ...data.filter(a => !existingIds.has(a.id))];
      });
      const idle = data.filter(a => a.status === "idle");
      for (const archive of idle) {
        try { await api.startIndexing(archive.id); } catch { /* indexing failures surface via toast/status */ }
      }
      showToast(
        idle.length > 0
          ? `Added ${data.length} archive(s). Indexing ${idle.length} in background.`
          : `Added ${data.length} archive(s). Already indexed.`,
        "success"
      );
      onNavigate?.("archives");
    } catch (err) {
      showToast(`Failed to add files: ${err instanceof Error ? err.message : "Unknown error"}`, "error");
    } finally {
      setIsScanning(false);
    }
  }, [onNavigate, showToast]);

  const deleteArchive = useCallback(async (id: string) => {
    try {
      await api.deleteArchive(id);
      setArchives(prev => prev.filter(a => a.id !== id));
      showToast("Archive removed.", "success");
    } catch (err) {
      showToast(`Failed to delete archive: ${err instanceof Error ? err.message : "Unknown error"}`, "error");
    }
  }, [showToast]);

  // Indexing
  const startIndexing = useCallback(async (archiveId: string) => {
    try {
      await api.startIndexing(archiveId);
      fetchArchives();
    } catch (err) {
      showToast(`Failed to start indexing: ${err instanceof Error ? err.message : "Unknown error"}`, "error");
    }
  }, [fetchArchives, showToast]);

  const pauseIndexing = useCallback(async (archiveId: string) => {
    try {
      await api.pauseIndexing(archiveId);
      fetchArchives();
    } catch (err) {
      showToast(`Failed to pause indexing: ${err instanceof Error ? err.message : "Unknown error"}`, "error");
    }
  }, [fetchArchives, showToast]);

  const cancelIndexing = useCallback(async (archiveId: string) => {
    try {
      await api.cancelIndexing(archiveId);
      fetchArchives();
    } catch (err) {
      showToast(`Failed to cancel indexing: ${err instanceof Error ? err.message : "Unknown error"}`, "error");
    }
  }, [fetchArchives, showToast]);

  const extractArchive = useCallback(async (archiveId: string) => {
    try {
      await api.extractArchive(archiveId);
      showToast("Content extraction started — the archive will show 'Ready' when done.", "success");
      // Poll archive status after a short delay to reflect "extracting" state
      setTimeout(fetchArchives, 1500);
    } catch (err) {
      showToast(`Extraction failed: ${err instanceof Error ? err.message : "Unknown error"}`, "error");
    }
  }, [fetchArchives, showToast]);

  // Initial load — fetch settings first to restore scan path, then load data
  useEffect(() => {
    const init = async () => {
      try {
        const s = await api.getSettings();
        if (s.zim_scan_path) setScanPathPersisted(s.zim_scan_path);
      } catch { /* settings unavailable — fall back to defaults */ }
      await Promise.all([fetchArchives(), fetchCategories()]);
    };
    init();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Single polling loop — replaces per-archive SSE streams which were
  // saturating Chromium's 6-connection-per-origin limit and blocking
  // search/article requests when many archives were indexing.
  // While any archive is in a transient state (indexing/extracting), poll
  // /api/archives every 3 seconds to refresh progress.  Stops polling once
  // every archive has reached a terminal state.
  useEffect(() => {
    const transient = archives.some(
      a => a.status === "indexing" || a.status === "extracting"
    );
    if (!transient) return;
    const id = setInterval(fetchArchives, 3000);
    return () => clearInterval(id);
  }, [archives, fetchArchives]);

  const value: AppContextValue = {
    theme,
    toggleTheme,
    archives,
    fetchArchives,
    deleteArchive,
    categories,
    fetchCategories,
    activeCategory,
    setActiveCategory,
    tabs,
    activeTabId,
    setActiveTabId,
    openArticleInTab,
    closeTab,
    updateTab,
    bookmarks,
    toggleBookmark,
    recentlyViewed,
    pushRecentlyViewed,
    scanPath,
    setScanPath: setScanPathPersisted,
    isScanning,
    scanZimFolder,
    pickAndScanDirectory,
    pickAndAddFiles,
    startIndexing,
    pauseIndexing,
    cancelIndexing,
    extractArchive,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be used within AppProvider");
  return ctx;
}
