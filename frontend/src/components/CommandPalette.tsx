import { useState, useEffect, useRef, useMemo } from "react";
import { useAppContext } from "../context/AppContext";
import { api } from "../services/api";

interface CommandItem {
  id: string;
  icon: string;
  title: string;
  subtitle?: string;
  action: () => void;
  keywords?: string;
}

/**
 * Command palette — opens with Ctrl/Cmd+K from anywhere.
 * Searches across archives, bookmarks, recently viewed, navigation,
 * and matching ZIM articles. Single keyboard-driven entry point to
 * everything in the app.
 */
export function CommandPalette({
  open,
  onClose,
  onNavigate,
}: {
  open: boolean;
  onClose: () => void;
  onNavigate: (view: string) => void;
}) {
  const {
    archives, categories, bookmarks, recentlyViewed,
    openArticleInTab, setActiveCategory, toggleTheme,
  } = useAppContext();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const [searchHits, setSearchHits] = useState<CommandItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset state every time the palette opens
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelected(0);
      setSearchHits([]);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Live fetch matching articles from the search API
  useEffect(() => {
    if (!open || query.trim().length < 2) { setSearchHits([]); return; }
    const t = setTimeout(async () => {
      try {
        const d = await api.search(query, { pageSize: 6 });
        setSearchHits(
          d.results.map(r => ({
            id: `art-${r.id}`,
            icon: "📄",
            title: r.title,
            subtitle: r.archive_title,
            action: () => { openArticleInTab(r.title, r.path, r.archive_id); onClose(); },
          }))
        );
      } catch { setSearchHits([]); }
    }, 220);
    return () => clearTimeout(t);
  }, [query, open, openArticleInTab, onClose]);

  // Build base items (always present)
  const baseItems = useMemo<CommandItem[]>(() => {
    const out: CommandItem[] = [];

    // Navigation
    out.push({ id: "nav-search", icon: "🔍", title: "Search", subtitle: "Open search panel",
      action: () => { onNavigate("search"); onClose(); }, keywords: "search find" });
    out.push({ id: "nav-archives", icon: "📚", title: "ZIM Archives", subtitle: "Manage archives",
      action: () => { onNavigate("archives"); onClose(); }, keywords: "archive zim" });
    out.push({ id: "nav-settings", icon: "⚙️", title: "Settings", subtitle: "App settings",
      action: () => { onNavigate("settings"); onClose(); }, keywords: "settings prefs" });

    // Actions
    out.push({ id: "act-theme", icon: "🌓", title: "Toggle theme", subtitle: "Switch light/dark",
      action: () => { toggleTheme(); onClose(); }, keywords: "theme dark light mode" });
    out.push({ id: "act-random", icon: "🎲", title: "Random article", subtitle: "Surprise me",
      action: async () => {
        try { const r = await api.randomArticle(); openArticleInTab(r.title, r.path, r.archive_id); }
        catch { /* */ }
        onClose();
      }, keywords: "random surprise discover"
    });

    // Categories
    categories.forEach(c => {
      out.push({
        id: `cat-${c.id}`,
        icon: "🏷",
        title: `Browse ${c.name}`,
        subtitle: "Category",
        action: () => { setActiveCategory(c); onNavigate("search"); onClose(); },
        keywords: `category ${c.name}`,
      });
    });

    // Archives — open archive manager view focusing one
    archives.slice(0, 15).forEach(a => {
      out.push({
        id: `arc-${a.id}`,
        icon: "📦",
        title: a.title || a.name,
        subtitle: `Archive · ${a.indexed_count.toLocaleString()} articles`,
        action: () => { onNavigate("archives"); onClose(); },
        keywords: `archive ${a.title} ${a.name}`,
      });
    });

    // Recently viewed
    recentlyViewed.slice(0, 6).forEach(r => {
      out.push({
        id: `rec-${r.id}`,
        icon: "⏱",
        title: r.title,
        subtitle: "Recently viewed",
        action: () => { openArticleInTab(r.title, r.path, r.archiveId); onClose(); },
        keywords: `recent ${r.title}`,
      });
    });

    // Bookmarks
    bookmarks.forEach(b => {
      out.push({
        id: `bkm-${b.id}`,
        icon: "⭐",
        title: b.title,
        subtitle: "Bookmark",
        action: () => { openArticleInTab(b.title, b.path, b.archiveId); onClose(); },
        keywords: `bookmark ${b.title}`,
      });
    });

    return out;
  }, [archives, categories, bookmarks, recentlyViewed,
      onNavigate, onClose, openArticleInTab, setActiveCategory, toggleTheme]);

  // Apply fuzzy-ish filter
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return baseItems.slice(0, 12);
    const items = baseItems.filter(it => {
      const haystack = `${it.title} ${it.subtitle || ""} ${it.keywords || ""}`.toLowerCase();
      return haystack.includes(q);
    });
    // Article search hits get appended (deduped by title)
    const seen = new Set(items.map(i => i.title));
    const more = searchHits.filter(s => !seen.has(s.title));
    return [...items, ...more].slice(0, 16);
  }, [baseItems, searchHits, query]);

  // Keyboard nav
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); }
      else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelected(s => Math.min(s + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelected(s => Math.max(0, s - 1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const item = filtered[selected];
        if (item) item.action();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, filtered, selected, onClose]);

  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0,
        background: "rgba(0,0,0,.4)",
        backdropFilter: "blur(2px)",
        zIndex: 9999,
        display: "flex", justifyContent: "center",
        paddingTop: "12vh",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: "min(640px, 92vw)",
          maxHeight: "70vh",
          background: "var(--bg-panel)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          boxShadow: "0 20px 60px rgba(0,0,0,.4)",
          display: "flex", flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command, search articles, jump to archive…"
            value={query}
            onChange={e => { setQuery(e.target.value); setSelected(0); }}
            style={{
              width: "100%", border: "none", outline: "none",
              background: "transparent", color: "var(--text-title)",
              fontSize: "1rem", fontFamily: "inherit",
            }}
          />
        </div>
        <div style={{ overflowY: "auto", flex: 1 }}>
          {filtered.length === 0 ? (
            <div style={{ padding: "32px 20px", textAlign: "center", color: "var(--text-muted)", fontSize: ".85rem" }}>
              No matches. Try a different word.
            </div>
          ) : (
            filtered.map((item, i) => (
              <div
                key={item.id}
                onClick={item.action}
                onMouseEnter={() => setSelected(i)}
                style={{
                  display: "flex", alignItems: "center", gap: 12,
                  padding: "10px 16px",
                  cursor: "pointer",
                  background: i === selected ? "var(--bg-active)" : "transparent",
                  borderLeft: i === selected ? "3px solid var(--primary)" : "3px solid transparent",
                }}
              >
                <span style={{ fontSize: "1.1rem", width: 24, textAlign: "center" }}>{item.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: ".92rem", fontWeight: 500, color: "var(--text-title)",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {item.title}
                  </div>
                  {item.subtitle && (
                    <div style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>
                      {item.subtitle}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
        <div style={{
          padding: "8px 14px", fontSize: ".7rem", color: "var(--text-muted)",
          borderTop: "1px solid var(--border)", background: "var(--bg-card)",
          display: "flex", justifyContent: "space-between",
        }}>
          <span>↑↓ navigate · ⏎ open · esc close</span>
          <span>Ctrl+K to reopen</span>
        </div>
      </div>
    </div>
  );
}
