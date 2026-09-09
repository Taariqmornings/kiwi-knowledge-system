import { useEffect, useState } from "react";
import { useAppContext } from "../context/AppContext";
import { api } from "../services/api";
import { useToast } from "./Toast";
import { VERSION } from "../version";
import { useReaderPrefs, type ColumnWidth, type ReaderTheme } from "../hooks/useReaderPrefs";

interface Health {
  articles: number;
  archives_by_status: Record<string, number>;
  db_size_mb: number;
  extracted_cache_mb: number;
  model_reachable: boolean;
  uptime_seconds: number;
  cpu_count: number;
  active_threads: number;
}

type Section = "library" | "reading" | "ai" | "system";

const SECTIONS: { id: Section; label: string; icon: string }[] = [
  { id: "library", label: "Library",   icon: "📚" },
  { id: "reading", label: "Reading",   icon: "📖" },
  { id: "ai",      label: "AI & data", icon: "✨" },
  { id: "system",  label: "System",    icon: "⚙" },
];

export function SettingsPanel() {
  const {
    archives, scanPath, setScanPath, isScanning,
    scanZimFolder, pickAndScanDirectory, pickAndAddFiles, fetchArchives,
  } = useAppContext();
  const isElectron = window.electronAPI?.isElectron ?? false;
  const { showToast } = useToast();
  const [health, setHealth] = useState<Health | null>(null);
  const [cleaning, setCleaning] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [section, setSection] = useState<Section>(() => {
    return (localStorage.getItem("kiwi-settings-section") as Section) || "library";
  });
  useEffect(() => { localStorage.setItem("kiwi-settings-section", section); }, [section]);

  const { prefs, setFontSize, setColumnWidth, setTheme } = useReaderPrefs();
  const widths: { val: ColumnWidth; label: string }[] = [
    { val: "narrow", label: "Narrow" }, { val: "normal", label: "Normal" }, { val: "wide", label: "Wide" },
  ];
  const themes: { val: ReaderTheme; label: string; bg: string; fg: string }[] = [
    { val: "light", label: "Light", bg: "#ffffff", fg: "#1f2328" },
    { val: "sepia", label: "Sepia", bg: "#f4ecd8", fg: "#5b4636" },
    { val: "dark",  label: "Dark",  bg: "#0d1117", fg: "#c9d1d9" },
  ];

  useEffect(() => {
    let alive = true;
    const tick = () => api.getHealth().then(h => { if (alive) setHealth(h); }).catch(() => {});
    tick();
    const id = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const onStopWork = async () => {
    setStopping(true);
    try {
      const r = await api.stopBackgroundWork();
      showToast(`Paused ${r.paused_jobs} background job(s). CPU is free now.`, "success");
      fetchArchives();
    } catch (e) {
      showToast(`Failed: ${e instanceof Error ? e.message : "Unknown"}`, "error");
    } finally {
      setStopping(false);
    }
  };

  const onCleanup = async () => {
    if (!confirm("Delete article rows with no readable content? Search & counts will be cleaner. This cannot be undone.")) return;
    setCleaning(true);
    try {
      const r = await api.cleanupStubs();
      showToast(`Removed ${r.deleted.toLocaleString()} stub articles (${r.before.toLocaleString()} → ${r.after.toLocaleString()}).`, "success");
      fetchArchives();
    } catch (e) {
      showToast(`Cleanup failed: ${e instanceof Error ? e.message : "Unknown"}`, "error");
    } finally {
      setCleaning(false);
    }
  };

  const indexed  = archives.filter(a => a.status === "indexed").length;
  const indexing = archives.filter(a => a.status === "indexing").length;
  const idle     = archives.filter(a => a.status === "idle").length;
  const failed   = archives.filter(a => a.status === "failed").length;

  return (
    <div className="settings-page">
      <div className="settings-header">
        <h1 className="settings-title">Settings</h1>
        <p className="settings-subtitle">Configure how Kiwi finds, reads and answers from your archives.</p>
      </div>

      <div className="settings-layout">
        {/* ── Sub-nav ───────────────────────────────────────── */}
        <nav className="settings-nav">
          {SECTIONS.map(s => (
            <button
              key={s.id}
              className={`settings-nav-item${section === s.id ? " active" : ""}`}
              onClick={() => setSection(s.id)}
            >
              <span className="settings-nav-icon">{s.icon}</span>
              <span>{s.label}</span>
            </button>
          ))}
        </nav>

        {/* ── Section body ──────────────────────────────────── */}
        <div className="settings-body">

          {section === "library" && (
            <>
              {isElectron && (
                <Card title="Add ZIM files" desc="Pick individual .zim files from disk. Each is registered, auto-categorised, and queued for indexing.">
                  <button className="btn btn-primary self-start" onClick={pickAndAddFiles} disabled={isScanning}>
                    {isScanning ? "Adding…" : "Add ZIM Files…"}
                  </button>
                </Card>
              )}

              <Card title="ZIM archive directory" desc="Folder Kiwi auto-scans on every launch. New archives are queued for indexing automatically.">
                <div className="flex gap-3">
                  <input
                    type="text"
                    className="search-input-field flex-1"
                    style={{ padding: "10px 14px" }}
                    placeholder="C:\Path\To\Your\ZIM\Files"
                    value={scanPath}
                    onChange={(e) => setScanPath(e.target.value)}
                  />
                  {isElectron && (
                    <button className="btn btn-secondary whitespace-nowrap" onClick={pickAndScanDirectory} disabled={isScanning}>
                      Browse…
                    </button>
                  )}
                  <button className="btn btn-primary whitespace-nowrap" onClick={scanZimFolder} disabled={isScanning}>
                    {isScanning ? "Scanning…" : "Scan & Index"}
                  </button>
                </div>
                {scanPath ? (
                  <StatusLine kind="ok">Auto-scan configured · this directory is scanned on every startup.</StatusLine>
                ) : (
                  <StatusLine kind="warn">No directory set. Enter a path above or click <strong>Browse…</strong> then <strong>Scan &amp; Index</strong>.</StatusLine>
                )}
              </Card>

              <Card title="Collection status" desc="Snapshot of every registered archive.">
                <div className="settings-stat-grid">
                  <Stat label="Total archives" value={archives.length.toString()} tint="default" />
                  <Stat label="Indexed"        value={indexed.toString()}        tint="success" />
                  <Stat label="Indexing now"   value={indexing.toString()}       tint="primary" />
                  <Stat label="Pending / failed" value={(idle + failed).toString()} tint="muted" />
                </div>
                {archives.length === 0 && (
                  <StatusLine kind="warn">No archives yet — use <strong>Add ZIM Files…</strong> or set a folder above.</StatusLine>
                )}
                {indexing > 0 && (
                  <StatusLine kind="info">Background indexing running · search works on already-indexed content.</StatusLine>
                )}
              </Card>
            </>
          )}

          {section === "reading" && (
            <>
              <Card title="Font size" desc={`Currently ${prefs.fontSize}px. Applies to every article reader.`}>
                <div className="flex gap-2">
                  <button className="btn btn-secondary btn-sm" onClick={() => setFontSize(prefs.fontSize - 1)} disabled={prefs.fontSize <= 12}>A−</button>
                  <button className="btn btn-secondary btn-sm" onClick={() => setFontSize(16)}>Reset</button>
                  <button className="btn btn-secondary btn-sm" onClick={() => setFontSize(prefs.fontSize + 1)} disabled={prefs.fontSize >= 22}>A+</button>
                </div>
              </Card>

              <Card title="Column width" desc="How wide article text can grow before wrapping.">
                <div className="flex gap-2">
                  {widths.map(w => (
                    <button
                      key={w.val}
                      className={`btn btn-sm ${prefs.columnWidth === w.val ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => setColumnWidth(w.val)}
                      style={{ minWidth: 96 }}
                    >
                      {w.label}
                    </button>
                  ))}
                </div>
              </Card>

              <Card title="Page colour" desc="Background tone for the reader. Changes apply immediately to open tabs.">
                <div className="flex gap-3">
                  {themes.map(t => (
                    <button
                      key={t.val}
                      onClick={() => setTheme(t.val)}
                      title={t.label}
                      style={{
                        background: t.bg, color: t.fg,
                        border: prefs.theme === t.val ? "2px solid var(--primary)" : "1px solid var(--border)",
                        borderRadius: 10, padding: "14px 22px", cursor: "pointer",
                        fontSize: "0.88rem", fontWeight: 600, minWidth: 110,
                        boxShadow: prefs.theme === t.val ? "0 2px 8px var(--primary-glow)" : "none",
                        transition: "all .15s ease",
                      }}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </Card>
            </>
          )}

          {section === "ai" && (
            <>
              <Card title="AI chat status" desc="Kiwi's offline answers come from your local Ollama server. Restart Ollama and refresh if it shows offline.">
                {health ? (
                  <div className="settings-stat-grid">
                    <Stat label="Ollama" value={health.model_reachable ? "● ready" : "● offline"} tint={health.model_reachable ? "success" : "danger"} />
                    <Stat label="Articles indexed" value={health.articles.toLocaleString()} tint="default" />
                    <Stat label="DB size" value={`${health.db_size_mb} MB`} tint="muted" />
                    <Stat label="CPU cores" value={String(health.cpu_count)} tint="muted" />
                  </div>
                ) : (
                  <div className="text-xs text-slate-500">Loading health…</div>
                )}
              </Card>

              <Card title="Database maintenance" desc="Clean up article entries that have no readable content (typically SPA redirect stubs from older ZIMs).">
                <button className="btn btn-secondary self-start" onClick={onCleanup} disabled={cleaning}>
                  {cleaning ? "Cleaning up…" : "Clean up stub articles"}
                </button>
              </Card>
            </>
          )}

          {section === "system" && (
            <>
              <Card title="Runtime" desc="Information about how Kiwi is currently running.">
                <div className="settings-stat-grid">
                  <Stat label="Runtime"       value={isElectron ? "Electron · Desktop" : "Browser · Dev"} tint="default" />
                  <Stat label="Search engine" value="SQLite FTS5 + BM25" tint="default" />
                  <Stat label="Mode"          value="Offline · Local-first" tint="default" />
                  <Stat label="Uptime"        value={health ? `${Math.floor(health.uptime_seconds / 60)} min` : "—"} tint="default" />
                </div>
              </Card>

              <Card title="Safety & resources" desc="Live snapshot of what Kiwi is using on your machine. Software cannot damage hardware — these stats just confirm nothing has leaked or run away.">
                {health ? (
                  <div className="settings-stat-grid">
                    <Stat label="Database"       value={`${health.db_size_mb} MB`}             tint="default" />
                    <Stat label="Extracted cache" value={`${health.extracted_cache_mb} MB`}    tint="muted" />
                    <Stat label="Background threads" value={String(health.active_threads)}     tint={health.active_threads > 20 ? "primary" : "default"} />
                    <Stat label="CPU cores available" value={String(health.cpu_count)}         tint="muted" />
                  </div>
                ) : (
                  <div className="text-xs text-slate-500">Loading…</div>
                )}
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 4 }}>
                  <button
                    className="btn btn-secondary self-start"
                    onClick={onStopWork}
                    disabled={stopping}
                    title="Pause all indexer threads — frees CPU instantly. Archives can be resumed any time from ZIM Archives."
                  >
                    {stopping ? "Stopping…" : "⏸ Stop all background work"}
                  </button>
                </div>
                <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", lineHeight: 1.55, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
                  <strong style={{ color: "var(--text-title)" }}>What's running, and what stops when you close Kiwi:</strong>
                  <ul style={{ margin: "8px 0 0 0", paddingLeft: "1.2em" }}>
                    <li><strong>Electron window</strong> — closes cleanly when you click ×.</li>
                    <li><strong>Kiwi backend</strong> (Python/uvicorn) — exits when you close the terminal window that <code>start.bat</code> opened. All indexer/extractor threads are daemons and exit with it.</li>
                    <li><strong>Ollama</strong> (the local AI server you started) — stays running on its own. Stop it from its tray icon, or close its terminal window.</li>
                    <li><strong>SQLite</strong> — every write is transactional, no corruption risk if the process is killed mid-write.</li>
                    <li><strong>Memory cap</strong> — at most: backend ≈ 300 MB · Ollama (Gemma 1B) ≈ 700 MB · Electron ≈ 400 MB.</li>
                    <li><strong>Disk usage</strong> — DB grows with indexed content; extracted cache grows when you use the extract feature. Both shown above. Nothing else is written outside <code>backend/data/</code>.</li>
                  </ul>
                </div>
              </Card>

              <Card title="About Kiwi" desc="Offline-first knowledge browser for ZIM archives.">
                <div className="settings-stat-grid">
                  <Stat label="Version" value={VERSION} tint="default" />
                  <Stat label="Privacy" value="100% local" tint="success" />
                </div>
              </Card>
            </>
          )}

        </div>
      </div>
    </div>
  );
}

/* ── Tiny presentational helpers ──────────────────────────────────── */

function Card({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <section className="settings-card">
      <div className="settings-card-head">
        <h2 className="settings-card-title">{title}</h2>
        {desc && <p className="settings-card-desc">{desc}</p>}
      </div>
      <div className="settings-card-body">{children}</div>
    </section>
  );
}

function Stat({ label, value, tint }: { label: string; value: string; tint: "default" | "primary" | "success" | "danger" | "muted" }) {
  const color = {
    default: "var(--text-title)",
    primary: "var(--primary)",
    success: "var(--success)",
    danger:  "var(--danger)",
    muted:   "var(--text-muted)",
  }[tint];
  return (
    <div className="settings-stat">
      <div className="settings-stat-label">{label}</div>
      <div className="settings-stat-value" style={{ color }}>{value}</div>
    </div>
  );
}

function StatusLine({ kind, children }: { kind: "ok" | "warn" | "info"; children: React.ReactNode }) {
  const colorMap = { ok: "var(--success)", warn: "var(--warning)", info: "var(--primary)" };
  const bgMap = {
    ok: "rgba(52,168,83,.08)", warn: "rgba(251,188,4,.08)", info: "rgba(66,133,244,.08)",
  };
  return (
    <div style={{
      fontSize: "0.78rem",
      color: colorMap[kind],
      background: bgMap[kind],
      border: `1px solid ${colorMap[kind]}33`,
      borderRadius: 8,
      padding: "8px 12px",
      display: "flex",
      alignItems: "center",
      gap: 8,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: colorMap[kind], flexShrink: 0 }} />
      <span>{children}</span>
    </div>
  );
}
