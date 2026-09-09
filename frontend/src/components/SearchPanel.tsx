import { useState, useEffect, useRef, useCallback } from "react";
import { useAppContext } from "../context/AppContext";
import { api, getBackendHost } from "../services/api";
import * as Icons from "./Icons";
import type { Article, Suggestion } from "../types";

const CATEGORY_ICONS: Record<string, string> = {
  HeartPulse: "🩺", Atom: "⚛️", Cpu: "💡", BookOpen: "📖",
  Globe: "🌍", Code: "💻", Calculator: "📐", Flame: "🔥",
  GraduationCap: "🎓", Library: "📚",
};

interface SearchMeta {
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

const EMPTY_META: SearchMeta = {
  total_count: 0, page: 1, page_size: 30, total_pages: 1,
  has_next: false, has_previous: false,
};

// Fallback label shown in the error hint before the real host resolves.
const DEFAULT_HOST_LABEL = "http://127.0.0.1:8000";

function Pagination({ meta, onPage }: { meta: SearchMeta; onPage: (p: number) => void }) {
  if (meta.total_pages <= 1) return null;
  const start = Math.max(1, meta.page - 2), end = Math.min(meta.total_pages, meta.page + 2);
  const pages = Array.from({ length: end - start + 1 }, (_, i) => start + i);
  return (
    <div className="flex items-center justify-center gap-1 mt-6 mb-2">
      <button className="btn btn-secondary btn-sm" disabled={!meta.has_previous} onClick={() => onPage(meta.page - 1)}><Icons.ArrowLeft /></button>
      {start > 1 && <span className="px-1 text-xs" style={{ color: "var(--text-muted)" }}>…</span>}
      {pages.map(p => (
        <button key={p} className={`btn btn-sm ${p === meta.page ? "btn-primary" : "btn-secondary"}`} onClick={() => onPage(p)}>{p}</button>
      ))}
      {end < meta.total_pages && <span className="px-1 text-xs" style={{ color: "var(--text-muted)" }}>…</span>}
      <button className="btn btn-secondary btn-sm" disabled={!meta.has_next} onClick={() => onPage(meta.page + 1)}><Icons.ArrowRight /></button>
    </div>
  );
}

export function SearchPanel({ onNavigate, onOpenChat }: { onNavigate: (view: string) => void; onOpenChat?: () => void }) {
  const {
    archives, categories, activeCategory, setActiveCategory,
    bookmarks, toggleBookmark, openArticleInTab,
    recentlyViewed,
  } = useAppContext();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Article[]>([]);
  const [meta, setMeta] = useState<SearchMeta>(EMPTY_META);
  const [searching, setSearching] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightedSuggestion, setHighlightedSuggestion] = useState(-1);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [backendUrl, setBackendUrl] = useState(DEFAULT_HOST_LABEL);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchHeaderRef = useRef<HTMLDivElement>(null);

  // Resolve the backend URL for the "Search failed" hint box.
  useEffect(() => {
    getBackendHost().then(setBackendUrl).catch(() => { /* keep default label */ });
  }, []);

  // Dismiss the suggestion dropdown only on EXPLICIT user intent:
  //   • Esc key
  //   • Space key   (per user request)
  //   • Mouse-down outside the search-header area
  //   • Selecting a suggestion or hitting Enter
  // Removing the blur-based timer means the dropdown stays open as long as
  // the user wants — no race condition between mouse-move and timer fire.
  useEffect(() => {
    if (!showSuggestions) return;
    const onDocMouseDown = (e: MouseEvent) => {
      const node = searchHeaderRef.current;
      if (node && !node.contains(e.target as Node)) {
        setShowSuggestions(false);
        setHighlightedSuggestion(-1);
      }
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [showSuggestions]);

  // Clear suggestions once the query drops below the autocomplete length.
  if (query.trim().length < 2 && suggestions.length > 0) {
    setSuggestions([]);
  }

  useEffect(() => {
    if (query.trim().length < 2) return;
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const d = await api.autocomplete(query);
        if (!cancelled) setSuggestions(d.suggestions || []);
      } catch (err) {
        console.error("Autocomplete failed:", err);
        if (!cancelled) setSuggestions([]);
      }
    }, 150);
    return () => { cancelled = true; clearTimeout(t); };
  }, [query]);

  const applyMeta = (d: SearchMeta) => setMeta({
    total_count: d.total_count, page: d.page, page_size: d.page_size,
    total_pages: d.total_pages, has_next: d.has_next, has_previous: d.has_previous,
  });

  const runSearch = useCallback(async (q: string, catId?: number, page = 1) => {
    if (!q.trim()) { setResults([]); setSearchError(null); return; }
    setSearching(true);
    setShowSuggestions(false);
    setSearchError(null);
    try {
      const params: { categoryId?: number; page?: number } = { page };
      if (catId !== undefined) params.categoryId = catId;
      else if (activeCategory) params.categoryId = activeCategory.id;
      const d = await api.search(q, { ...params, pageSize: 30 });
      setResults(d.results || []);
      applyMeta(d);
    } catch (err) {
      console.error("Search failed:", err);
      setSearchError(err instanceof Error ? err.message : "Search request failed");
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, [activeCategory]);

  const browseCategory = useCallback(async (catId: number, page = 1) => {
    setSearching(true);
    setShowSuggestions(false);
    setSearchError(null);
    try {
      const d = await api.browseCategory(catId, { page, pageSize: 30 });
      setResults(d.results || []);
      applyMeta(d);
    } catch (err) {
      console.error("Browse failed:", err);
      setSearchError(err instanceof Error ? err.message : "Category browse failed");
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  // Clear stale results when the query is emptied.
  if (!query.trim() && results.length > 0) {
    setResults([]);
    setMeta(EMPTY_META);
  }

  // Auto-search as user types (debounced) — Google-style live search
  useEffect(() => {
    if (query.trim().length < 2) return;
    const t = setTimeout(() => { runSearch(query); }, 350);
    return () => clearTimeout(t);
  }, [query, runSearch]);

  const goToPage = (p: number) => {
    if (!query.trim() && activeCategory) browseCategory(activeCategory.id, p);
    else runSearch(query, undefined, p);
  };

  const handleCategoryClick = (cat: typeof categories[0]) => {
    if (activeCategory?.id === cat.id) { setActiveCategory(null); setResults([]); return; }
    setActiveCategory(cat);
    if (query.trim()) runSearch(query, cat.id);
    else browseCategory(cat.id);
  };

  const renderTitle = (r: Article) =>
    r.title_highlight ? <span dangerouslySetInnerHTML={{ __html: r.title_highlight }} /> : <>{r.title}</>;

  const renderSnippet = (r: Article) => {
    if (r.snippet) return <span dangerouslySetInnerHTML={{ __html: r.snippet }} />;
    if (r.summary) return <>{r.summary.substring(0, 240)}…</>;
    return null;
  };

  const isBookmarked = (r: Article) => bookmarks.some(b => b.path === r.path && b.archiveId === r.archive_id);

  const noArchives = archives.length === 0;

  return (
    <div className="flex-1 flex flex-col overflow-y-auto" style={{ padding: "28px 32px" }}>

      {/* Search bar */}
      <div style={{ maxWidth: 720, margin: "0 auto", width: "100%" }}>
        {results.length === 0 && !searching && (
          <div className="text-center" style={{ marginBottom: 24 }}>
            <h1 style={{ fontSize: "2.8rem", fontWeight: 800, letterSpacing: "-1px", marginBottom: 6, lineHeight: 1 }}>
              <span style={{ color: "#6b7280" }}>Ki</span><span style={{ color: "#4285f4" }}>wi</span>
            </h1>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Your offline knowledge base</p>
            {onOpenChat && (
              <div>
                <button className="ask-kiwi-hero" onClick={onOpenChat} title="Open the offline AI chat">
                  <Icons.Sparkle /> Ask Kiwi anything
                </button>
              </div>
            )}
          </div>
        )}

        <div className="search-header" ref={searchHeaderRef} style={{ marginBottom: 14 }}>
          <div className="search-input-wrapper">
            <span className="search-icon-left"><Icons.Search /></span>
            <input
              ref={inputRef}
              type="text"
              className="search-input-field"
              placeholder={activeCategory ? `Search in ${activeCategory.name}…` : "Search anything…"}
              value={query}
              onChange={e => {
                setQuery(e.target.value);
                setShowSuggestions(true);
                setHighlightedSuggestion(-1);
              }}
              onKeyDown={e => {
                // Arrow-key navigation through the suggestion list
                if (e.key === "ArrowDown" && showSuggestions && suggestions.length) {
                  e.preventDefault();
                  setHighlightedSuggestion(i => Math.min(suggestions.length - 1, i + 1));
                } else if (e.key === "ArrowUp" && showSuggestions && suggestions.length) {
                  e.preventDefault();
                  setHighlightedSuggestion(i => Math.max(-1, i - 1));
                } else if (e.key === "Enter") {
                  if (highlightedSuggestion >= 0 && suggestions[highlightedSuggestion]) {
                    e.preventDefault();
                    const s = suggestions[highlightedSuggestion];
                    setShowSuggestions(false);
                    setHighlightedSuggestion(-1);
                    openArticleInTab(s.title, s.path, s.archive_id);
                  } else {
                    setShowSuggestions(false);
                    runSearch(query);
                  }
                } else if (e.key === "Escape") {
                  setShowSuggestions(false);
                  setHighlightedSuggestion(-1);
                } else if (e.key === " ") {
                  // Space dismisses the dropdown but still inserts the space
                  // in the input so multi-word queries keep working.
                  setShowSuggestions(false);
                  setHighlightedSuggestion(-1);
                }
              }}
              onFocus={() => { if (query.trim().length >= 2) setShowSuggestions(true); }}
              /* No onBlur close — the document-mousedown listener handles
                 outside clicks, and Esc / Space / item-select close it too.
                 This way the dropdown never disappears while the user is
                 trying to mouse onto it. */
            />
            {query && (
              <button
                style={{ position: "absolute", right: 12, background: "var(--primary)", color: "#fff", border: "none", borderRadius: 20, padding: "5px 16px", fontSize: "0.85rem", fontWeight: 600, cursor: "pointer" }}
                onClick={() => runSearch(query)}
              >
                Search
              </button>
            )}
          </div>

          {showSuggestions && suggestions.length > 0 && (
            <div className="autocomplete-dropdown">
              {suggestions.map((s, i) => (
                <div
                  key={i}
                  className={`autocomplete-item${i === highlightedSuggestion ? " autocomplete-item-active" : ""}`}
                  onMouseEnter={() => setHighlightedSuggestion(i)}
                  onMouseDown={(e) => {
                    // mousedown (not click) fires before any blur side-effects
                    e.preventDefault();
                    setShowSuggestions(false);
                    setHighlightedSuggestion(-1);
                    openArticleInTab(s.title, s.path, s.archive_id);
                  }}
                >
                  <span style={{ color: "var(--text-muted)", flexShrink: 0 }}><Icons.Search /></span>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div className="autocomplete-title">{s.title}</div>
                    <div className="autocomplete-meta">{s.archive_title}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Category chips */}
        {categories.length > 0 && (
          <div className="category-chips" style={{ marginBottom: 24 }}>
            {categories.map(cat => (
              <button
                key={cat.id}
                className={`category-chip${activeCategory?.id === cat.id ? " active" : ""}`}
                onClick={() => handleCategoryClick(cat)}
              >
                <span className="chip-icon">{CATEGORY_ICONS[cat.icon] ?? "📚"}</span>
                {cat.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Content */}
      <div style={{ maxWidth: 720, margin: "0 auto", width: "100%", flex: 1 }}>

        {noArchives && !searching && (
          <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 12, padding: "28px", textAlign: "center" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: 10 }}>📂</div>
            <div style={{ fontWeight: 700, fontSize: "1rem", marginBottom: 8, color: "var(--text-title)" }}>No ZIM archives yet</div>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", maxWidth: 360, margin: "0 auto 16px" }}>
              Go to <strong>Settings</strong> → <strong>Add ZIM Files…</strong> to pick files from your disk, or set a folder and click <strong>Scan &amp; Index</strong>.
            </p>
            <button className="btn btn-primary" onClick={() => onNavigate("settings")}>Go to Settings</button>
          </div>
        )}

        {searching && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 12, padding: "60px 0" }}>
            <div style={{ width: 32, height: 32, border: "3px solid var(--border)", borderTopColor: "var(--primary)", borderRadius: "50%", animation: "spin .7s linear infinite" }} />
            <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Searching…</span>
          </div>
        )}

        {searchError && !searching && (
          <div style={{ background: "rgba(234,67,53,0.08)", border: "1px solid rgba(234,67,53,0.3)", borderRadius: 12, padding: "16px 20px", color: "var(--danger)" }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Search failed</div>
            <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>{searchError}</div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 8 }}>
              Backend URL: <code>{backendUrl}</code>. If this persists, the backend may not be running.
            </div>
          </div>
        )}

        {!searching && results.length > 0 && (
          <>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: 10 }}>
              About <strong>{meta.total_count.toLocaleString()}</strong> results
              {activeCategory && <span> in <strong>{activeCategory.name}</strong></span>}
              {meta.total_pages > 1 && <span> · Page {meta.page} of {meta.total_pages}</span>}
            </div>
            <div className="search-results-list">
              {results.map(r => (
                <div key={r.id} className="search-result-item">
                  <div className="search-result-source">
                    <span style={{ background: "var(--bg-hover)", borderRadius: 4, padding: "1px 6px", fontSize: "0.72rem" }}>{r.archive_title}</span>
                  </div>
                  <div className="search-result-title" onClick={() => openArticleInTab(r.title, r.path, r.archive_id)}>
                    {renderTitle(r)}
                  </div>
                  <div className="search-result-path">{r.path}</div>
                  {renderSnippet(r) && <div className="search-result-snippet">{renderSnippet(r)}</div>}
                  <div className="search-result-actions">
                    <button
                      style={{ fontSize: "0.78rem", color: isBookmarked(r) ? "#fbbc04" : "var(--text-muted)", cursor: "pointer", background: "none", border: "none", display: "flex", alignItems: "center", gap: 4 }}
                      onClick={() => toggleBookmark(r.title, r.path, r.archive_id)}
                    >
                      <Icons.Bookmark active={isBookmarked(r)} />
                      {isBookmarked(r) ? "Saved" : "Save"}
                    </button>
                    <button
                      style={{ fontSize: "0.78rem", color: "var(--primary)", cursor: "pointer", background: "none", border: "none", fontWeight: 600 }}
                      onClick={() => openArticleInTab(r.title, r.path, r.archive_id)}
                    >
                      Read →
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <Pagination meta={meta} onPage={goToPage} />
          </>
        )}

        {!searching && results.length === 0 && query.trim() && (
          <div style={{ textAlign: "center", padding: "48px 0" }}>
            <div style={{ fontSize: "2rem", marginBottom: 10 }}>🔍</div>
            <div style={{ fontWeight: 700, marginBottom: 6, color: "var(--text-title)" }}>No results for "{query}"</div>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              Try different keywords, or make sure archives are fully indexed.
            </p>
          </div>
        )}

        {!searching && results.length === 0 && !query.trim() && activeCategory && (
          <div style={{ textAlign: "center", padding: "48px 0" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: 10 }}>{CATEGORY_ICONS[activeCategory.icon] ?? "📚"}</div>
            <div style={{ fontWeight: 700, marginBottom: 6, color: "var(--text-title)" }}>{activeCategory.name} — no articles yet</div>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              Scan a ZIM archive that matches this category. Articles appear here after indexing finishes.
            </p>
          </div>
        )}

        {/* Discovery row + recently viewed — shown on the home (no query, no category) ─── */}
        {!searching && results.length === 0 && !query.trim() && !activeCategory && (
          <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
            {/* Discovery actions */}
            {archives.length > 0 && (
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button
                  className="btn btn-primary"
                  onClick={async () => {
                    try {
                      const r = await api.randomArticle();
                      openArticleInTab(r.title, r.path, r.archive_id);
                    } catch { /* no articles yet */ }
                  }}
                  style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
                >
                  🎲 Surprise me
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => onNavigate("archives")}
                >
                  📚 Browse archives
                </button>
              </div>
            )}

            {/* Recently viewed */}
            {recentlyViewed.length > 0 && (
              <div>
                <h2 style={{
                  fontSize: "0.8rem", fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.06em", color: "var(--text-muted)", marginBottom: 12,
                }}>
                  Recently viewed
                </h2>
                <div style={{
                  display: "flex", gap: 10, overflowX: "auto",
                  paddingBottom: 8, scrollSnapType: "x mandatory",
                }}>
                  {recentlyViewed.slice(0, 12).map((b) => (
                    <div
                      key={b.id}
                      onClick={() => openArticleInTab(b.title, b.path, b.archiveId)}
                      style={{
                        flex: "0 0 220px",
                        scrollSnapAlign: "start",
                        background: "var(--bg-panel)",
                        border: "1px solid var(--border)",
                        borderRadius: 10,
                        padding: "12px 14px",
                        cursor: "pointer",
                        transition: "border-color .15s, transform .15s",
                      }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--primary)"; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; }}
                    >
                      <div style={{
                        fontSize: "0.9rem", fontWeight: 600, color: "var(--text-title)",
                        overflow: "hidden", textOverflow: "ellipsis",
                        display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
                        marginBottom: 6, minHeight: "2.5em",
                      }}>
                        {b.title}
                      </div>
                      <div style={{
                        fontSize: "0.72rem", color: "var(--text-muted)",
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      }}>
                        {archives.find(a => a.id === b.archiveId)?.title ?? "ZIM"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Bookmarks */}
            {bookmarks.length > 0 && (
              <div>
                <h2 style={{
                  fontSize: "0.8rem", fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.06em", color: "var(--text-muted)", marginBottom: 12,
                }}>
                  Bookmarks
                </h2>
                <div className="cards-grid">
                  {bookmarks.map((b, i) => (
                    <div key={i} className="premium-card">
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                        <div className="card-title" style={{ fontSize: "0.9rem" }}>{b.title}</div>
                        <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", flexShrink: 0 }}>
                          {archives.find(a => a.id === b.archiveId)?.title ?? "ZIM"}
                        </span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", paddingTop: 8, borderTop: "1px solid var(--border)" }}>
                        <button style={{ color: "var(--danger)", cursor: "pointer", background: "none", border: "none" }} onClick={() => toggleBookmark(b.title, b.path, b.archiveId)}>Remove</button>
                        <button style={{ color: "var(--primary)", fontWeight: 600, cursor: "pointer", background: "none", border: "none" }} onClick={() => openArticleInTab(b.title, b.path, b.archiveId)}>Open →</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
