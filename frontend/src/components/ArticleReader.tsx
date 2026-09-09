import { useRef, useCallback, useState, useEffect } from "react";
import { useAppContext } from "../context/AppContext";
import { api, getBackendHost } from "../services/api";
import * as Icons from "./Icons";
import { useReaderPrefs } from "../hooks/useReaderPrefs";
// ReaderControls moved to the Settings page — preferences sync via the
// `kiwi-prefs-changed` custom event handled in useReaderPrefs.

/**
 * Article reader.
 *
 * Communication with the article iframe is done via postMessage:
 *   iframe → parent:
 *     {type:'kiwi-navigate', archiveId, path, title, newTab}   link clicked
 *     {type:'kiwi-page-loaded', archiveId, path, title}        page loaded
 *     {type:'kiwi-scroll', percent}                            scroll progress
 *     {type:'kiwi-key', key:'cmd-k'}                           Ctrl+K bubbled up
 *   parent → iframe:
 *     {type:'kiwi-set-theme', theme}     live theme change
 *     {type:'kiwi-set-font-size', size}  live font change
 *     {type:'kiwi-set-column-width', width}
 *
 * Back/forward now work because navigation flows through the parent
 * (which mutates Tab.history correctly).
 */
interface ArticleReaderProps {
  onToggleChat?: () => void;
  chatOpen?: boolean;
  sidebarCollapsed?: boolean;
  onOpenSidebar?: () => void;
}

export function ArticleReader({ onToggleChat, chatOpen, sidebarCollapsed, onOpenSidebar }: ArticleReaderProps = {}) {
  const {
    tabs, activeTabId, updateTab, closeTab,
    bookmarks, toggleBookmark, openArticleInTab,
  } = useAppContext();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const activeTab = tabs.find(t => t.id === activeTabId);
  const [articleUrl, setArticleUrl] = useState("");
  const [iframeError, setIframeError] = useState<string | null>(null);
  const [urlLoading, setUrlLoading] = useState(true);
  const { prefs } = useReaderPrefs();

  // ── Build the iframe URL when the tab changes (not on pref changes) ─
  // Resetting the loading state in response to a tab change is done during
  // render (the React-recommended derived-state pattern) so no effect has to
  // synchronously write state as a side effect.
  const tabKey = activeTab ? `${activeTab.archiveId}/${activeTab.path}` : "";
  const [lastTabKey, setLastTabKey] = useState(tabKey);
  if (lastTabKey !== tabKey) {
    setLastTabKey(tabKey);
    if (!activeTab) {
      setArticleUrl("");
    } else {
      setUrlLoading(true);
      setIframeError(null);
    }
  }

  useEffect(() => {
    if (!activeTab) return;
    let cancelled = false;
    api.getArticleUrl(activeTab.archiveId, activeTab.path, prefs.theme, {
      font: prefs.fontSize,
      width: prefs.columnWidth,
    }).then(url => {
      if (cancelled) return;
      setArticleUrl(url);
      setUrlLoading(false);
    }).catch(err => {
      if (cancelled) return;
      setIframeError(
        `Failed to build article URL: ${err instanceof Error ? err.message : "Unknown error"}`
      );
      setUrlLoading(false);
    });
    return () => { cancelled = true; };
    // Live pref changes go through postMessage instead of reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabKey]);

  // ── Push pref changes into the iframe with no page reload ─────────
  useEffect(() => {
    const win = iframeRef.current?.contentWindow;
    if (!win) return;
    try {
      win.postMessage({ type: "kiwi-set-theme", theme: prefs.theme }, "*");
      win.postMessage({ type: "kiwi-set-font-size", size: prefs.fontSize }, "*");
      win.postMessage({ type: "kiwi-set-column-width", width: prefs.columnWidth }, "*");
    } catch { /* iframe might still be loading */ }
  }, [prefs]);

  // ── postMessage listener: navigation + title ──────────────────────
  useEffect(() => {
    if (!activeTab) return;

    const onMessage = (event: MessageEvent) => {
      // Only trust messages that come from our own backend origin — a page
      // from any other site must never be able to drive navigation here.
      getBackendHost().then(host => {
        if (event.origin !== host) return;
        const data = event.data;
        if (!data || typeof data !== "object" || !data.type) return;

        if (data.type === "kiwi-navigate") {
          const { archiveId, path, title, fromArchiveId, fromPath, fromTitle, sameTab } = data as {
            archiveId: string; path: string; title?: string;
            fromArchiveId?: string; fromPath?: string; fromTitle?: string;
            sameTab?: boolean;
          };

          // Default behaviour: open every link in a NEW tab whose history is
          // pre-seeded with the source article — so the back arrow in the new
          // tab returns to where the user came from, across archives.
          // `sameTab=true` (alt-click in the iframe) overrides this for power
          // users who want browser-style in-place navigation.
          if (sameTab && archiveId === activeTab.archiveId) {
            if (path === activeTab.path) return;
            const trimmed = activeTab.history.slice(0, activeTab.historyIndex + 1);
            trimmed.push({ path, archiveId, title: title || "Loading…" });
            updateTab(activeTab.id, {
              path,
              title: title || "Loading…",
              history: trimmed,
              historyIndex: trimmed.length - 1,
            });
            return;
          }

          const fromEntry =
            fromArchiveId && fromPath
              ? { archiveId: fromArchiveId, path: fromPath, title: fromTitle || activeTab.title }
              : { archiveId: activeTab.archiveId, path: activeTab.path, title: activeTab.title };
          openArticleInTab(title || "Loading…", path, archiveId, { from: fromEntry });
        } else if (data.type === "kiwi-page-loaded") {
          if (data.title && data.title !== "Loading…") {
            updateTab(activeTab.id, { title: data.title });
            const idx = activeTab.historyIndex;
            if (activeTab.history[idx]) {
              const newHist = [...activeTab.history];
              newHist[idx] = { ...newHist[idx], title: data.title };
              updateTab(activeTab.id, { history: newHist });
            }
          }
          // Restore saved scroll position for this history entry
          const entry = activeTab.history[activeTab.historyIndex];
          if (entry?.scrollPercent && iframeRef.current?.contentWindow) {
            iframeRef.current.contentWindow.postMessage(
              { type: "kiwi-restore-scroll", percent: entry.scrollPercent },
              "*"
            );
          }
        } else if (data.type === "kiwi-scroll") {
          // Persist the latest scroll fraction on the active history entry
          if (typeof data.percent === "number" && activeTab.history[activeTab.historyIndex]) {
            const newHist = [...activeTab.history];
            newHist[activeTab.historyIndex] = {
              ...newHist[activeTab.historyIndex],
              scrollPercent: data.percent / 100, // kiwi.js sends percent 0-100
            };
            updateTab(activeTab.id, { history: newHist });
          }
        }
      }).catch(() => { /* backend host unavailable — drop the message */ });
    };

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [activeTab, updateTab, openArticleInTab]);

  // ── Back / forward / reload ───────────────────────────────────────
  const canBack = !!activeTab && activeTab.historyIndex > 0;
  const canForward = !!activeTab && activeTab.historyIndex < activeTab.history.length - 1;

  const handleBack = useCallback(() => {
    if (!activeTab || !canBack) return;
    const newIndex = activeTab.historyIndex - 1;
    const prev = activeTab.history[newIndex];
    updateTab(activeTab.id, {
      path: prev.path,
      archiveId: prev.archiveId,
      title: prev.title,
      historyIndex: newIndex,
    });
  }, [activeTab, canBack, updateTab]);

  const handleForward = useCallback(() => {
    if (!activeTab || !canForward) return;
    const newIndex = activeTab.historyIndex + 1;
    const next = activeTab.history[newIndex];
    updateTab(activeTab.id, {
      path: next.path,
      archiveId: next.archiveId,
      title: next.title,
      historyIndex: newIndex,
    });
  }, [activeTab, canForward, updateTab]);

  const handleReload = useCallback(() => {
    if (!activeTab) return;
    setIframeError(null);
    setUrlLoading(true);
    api.getArticleUrl(activeTab.archiveId, activeTab.path, prefs.theme, {
      font: prefs.fontSize, width: prefs.columnWidth,
    }).then(url => {
      setArticleUrl(url + (url.includes("?") ? "&" : "?") + "_r=" + Date.now());
      setUrlLoading(false);
    });
  }, [activeTab, prefs]);

  const onIframeError = useCallback(() => {
    setIframeError("Failed to load article — check that the ZIM file still exists at the original path.");
  }, []);

  // ── Alt+Left / Alt+Right + mouse back/forward (button 3/4) ─────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && e.key === "ArrowLeft")  { e.preventDefault(); handleBack(); }
      else if (e.altKey && e.key === "ArrowRight") { e.preventDefault(); handleForward(); }
    };
    const onMouse = (e: MouseEvent) => {
      // Browser-style "back" (button 3) and "forward" (button 4) mouse buttons
      if (e.button === 3) { e.preventDefault(); handleBack(); }
      else if (e.button === 4) { e.preventDefault(); handleForward(); }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mouseup", onMouse);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mouseup", onMouse);
    };
  }, [handleBack, handleForward]);

  if (!activeTab) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: "var(--text-muted)" }}>
        No article selected.
      </div>
    );
  }

  const isBkm = bookmarks.some(b => b.path === activeTab.path && b.archiveId === activeTab.archiveId);

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ height: "100%" }}>
      {/* Reader toolbar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        background: "var(--bg-panel)",
        borderBottom: "1px solid var(--border)",
        padding: "8px 14px",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", gap: 2, borderRight: "1px solid var(--border)", paddingRight: 10 }}>
          {sidebarCollapsed && onOpenSidebar && (
            <button
              className="reader-nav-btn"
              onClick={onOpenSidebar}
              title="Show navigation (Ctrl+B)"
              aria-label="Open sidebar"
              style={{ fontSize: 18, fontWeight: 500 }}
            >
              ☰
            </button>
          )}
          <button
            className="reader-nav-btn"
            onClick={handleBack}
            disabled={!canBack}
            title="Back (Alt+←)"
            aria-label="Back"
          >
            <Icons.ArrowLeft />
          </button>
          <button
            className="reader-nav-btn"
            onClick={handleForward}
            disabled={!canForward}
            title="Forward (Alt+→)"
            aria-label="Forward"
          >
            <Icons.ArrowRight />
          </button>
          <button
            className="reader-nav-btn"
            onClick={handleReload}
            title="Reload page"
            aria-label="Reload"
          >
            <Icons.Refresh />
          </button>
        </div>

        <div style={{
          flex: 1, minWidth: 0,
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: "5px 12px",
          display: "flex", alignItems: "center", gap: 8,
          fontSize: ".78rem", fontFamily: "monospace",
          color: "var(--text-muted)",
        }}>
          <span style={{
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1,
          }}>
            zim://{activeTab.archiveId.substring(0, 8)}/{activeTab.path}
          </span>
          <span style={{
            color: "var(--text-muted)", background: "var(--bg-hover)",
            padding: "1px 6px", borderRadius: 4, fontSize: ".7rem", fontWeight: 600,
          }}>
            {activeTab.history.length > 1
              ? `${activeTab.historyIndex + 1}/${activeTab.history.length}`
              : "HTML"}
          </span>
        </div>

        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {onToggleChat && (
            <button
              className={`ask-kiwi-btn${chatOpen ? " active" : ""}`}
              onClick={onToggleChat}
              title="Ask Kiwi about this article (offline AI)"
            >
              <Icons.Sparkle /> Ask Kiwi
            </button>
          )}
          <button
            className="btn btn-secondary btn-icon"
            onClick={() => toggleBookmark(activeTab.title, activeTab.path, activeTab.archiveId)}
            title={isBkm ? "Remove bookmark" : "Bookmark this article"}
            style={{ color: isBkm ? "#fbbc04" : "var(--text-muted)" }}
          >
            <Icons.Bookmark active={isBkm} />
          </button>
          <button
            className="btn btn-secondary btn-icon"
            onClick={() => closeTab(activeTab.id)}
            title="Close tab"
            style={{ color: "var(--text-muted)" }}
          >
            <Icons.Close />
          </button>
        </div>
      </div>

      {/* Iframe + overlays */}
      <div style={{ flex: 1, position: "relative", overflow: "hidden", background: "var(--bg-panel)" }}>
        {urlLoading && (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            gap: 12, background: "var(--bg-panel)", zIndex: 10,
          }}>
            <div style={{
              width: 32, height: 32,
              border: "3px solid var(--border)",
              borderTopColor: "var(--primary)",
              borderRadius: "50%",
              animation: "spin .7s linear infinite",
            }} />
            <span style={{ color: "var(--text-muted)", fontSize: ".85rem" }}>Loading article…</span>
          </div>
        )}

        {iframeError && !urlLoading && (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12,
            background: "var(--bg-panel)", zIndex: 10, padding: 24, textAlign: "center",
          }}>
            <div style={{ color: "var(--danger)", fontWeight: 700, fontSize: "1rem" }}>
              Failed to load article
            </div>
            <div style={{ color: "var(--text-muted)", fontSize: ".85rem", maxWidth: 380 }}>
              {iframeError}
            </div>
            <button className="btn btn-primary" onClick={handleReload}>Retry</button>
          </div>
        )}

        <iframe
          ref={iframeRef}
          src={articleUrl}
          onError={onIframeError}
          title="Article content"
          style={{ width: "100%", height: "100%", border: "none", background: "var(--bg-panel)" }}
        />

      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
