import { useAppContext } from "../context/AppContext";
import * as Icons from "./Icons";

function StatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = {
    indexed:    "badge-indexed",
    indexing:   "badge-indexing",
    idle:       "badge-idle",
    failed:     "badge-failed",
    paused:     "badge-paused",
    extracting: "badge-extracting",
    ready:      "badge-ready",
  };
  const label: Record<string, string> = {
    indexed:    "✓ Indexed",
    indexing:   "⟳ Indexing",
    idle:       "Pending",
    failed:     "Failed",
    paused:     "Paused",
    extracting: "⟳ Extracting",
    ready:      "✦ Ready",
  };
  return (
    <span className={`badge ${cls[status] ?? "badge-idle"}`}>
      {label[status] ?? status}
    </span>
  );
}

function fmtSize(bytes: number) {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(0)} MB`;
  return `${(bytes / 1e3).toFixed(0)} KB`;
}

export function ArchiveManager({ onNavigate }: { onNavigate: (view: string) => void }) {
  const {
    archives,
    deleteArchive,
    startIndexing,
    pauseIndexing,
    cancelIndexing,
    extractArchive,
  } = useAppContext();

  return (
    <div className="flex-1 overflow-y-auto" style={{ padding: "24px 28px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--text-title)" }}>ZIM Archives</h1>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 2 }}>
            {archives.length} archive{archives.length !== 1 ? "s" : ""} registered
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => onNavigate("settings")}>+ Add Archives</button>
      </div>

      {archives.length === 0 ? (
        <div style={{ textAlign: "center", padding: "60px 0", border: "2px dashed var(--border)", borderRadius: 16 }}>
          <div style={{ fontSize: "3rem", marginBottom: 12 }}>📦</div>
          <div style={{ fontWeight: 700, fontSize: "1rem", marginBottom: 8, color: "var(--text-title)" }}>No archives yet</div>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", maxWidth: 340, margin: "0 auto 20px" }}>
            Add ZIM files from Settings to register and index them for search.
          </p>
          <button className="btn btn-primary" onClick={() => onNavigate("settings")}>Go to Settings</button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {archives.map(archive => {
            const pct = archive.article_count > 0
              ? Math.min((archive.indexed_count / archive.article_count) * 100, 100)
              : 0;
            const barColor =
              archive.status === "ready"      ? "#22c55e"
              : archive.status === "indexed"  ? "var(--success)"
              : archive.status === "indexing" || archive.status === "extracting"
                                              ? "var(--primary)"
              : "var(--warning)";

            return (
              <div key={archive.id} className="glass-panel" style={{ padding: "16px 20px" }}>
                {/* Title + badge + delete */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--text-title)" }}>
                        {archive.title || archive.name}
                      </span>
                      {archive.language && (
                        <span style={{ fontSize: "0.68rem", background: "var(--bg-hover)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 5px", color: "var(--text-muted)", fontFamily: "monospace" }}>
                          {archive.language.toUpperCase()}
                        </span>
                      )}
                      <StatusBadge status={archive.status} />
                      {archive.is_extracted && archive.status !== "ready" && (
                        <span style={{ fontSize: "0.68rem", color: "#22c55e", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.3)", borderRadius: 10, padding: "1px 6px", fontWeight: 600 }}>
                          extracted
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: 2, fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "90%" }}>
                      {archive.path}
                    </div>
                  </div>
                  <button
                    className="btn btn-secondary btn-icon"
                    style={{ color: "var(--danger)", flexShrink: 0, marginLeft: 8 }}
                    onClick={() => deleteArchive(archive.id)}
                    title="Remove"
                  >
                    <Icons.Trash />
                  </button>
                </div>

                {/* Stats */}
                {(() => {
                  const stats: { label: string; val: string }[] = [
                    { label: "Size",     val: fmtSize(archive.size_bytes) },
                    { label: "Articles", val: archive.article_count.toLocaleString() },
                    { label: "Indexed",  val: archive.indexed_count.toLocaleString() },
                    { label: "Date",     val: archive.date || "—" },
                  ];
                  return (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 6, background: "var(--bg-card)", borderRadius: 8, padding: "8px 12px", marginBottom: 10 }}>
                      {stats.map(({ label, val }) => (
                        <div key={label}>
                          <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginBottom: 1 }}>{label}</div>
                          <div style={{ fontSize: "0.88rem", fontWeight: 600, color: "var(--text-title)", fontFamily: "monospace" }}>{val}</div>
                        </div>
                      ))}
                    </div>
                  );
                })()}

                {/* Progress bar */}
                <div style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: 3 }}>
                    <span>Index progress</span>
                    <span>{pct.toFixed(1)}%</span>
                  </div>
                  <div style={{ height: 5, background: "var(--bg-hover)", borderRadius: 3, overflow: "hidden" }}>
                    <div style={{ height: "100%", borderRadius: 3, width: `${pct}%`, background: barColor, transition: "width .4s ease" }} />
                  </div>
                </div>

                {/* Extraction status note */}
                {archive.status === "extracting" && (
                  <div style={{ fontSize: "0.75rem", color: "var(--primary)", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ animation: "spin .8s linear infinite", display: "inline-block" }}>⟳</span>
                    Extracting content to internal store… ZIM file still needed until this completes.
                  </div>
                )}
                {archive.status === "ready" && (
                  <div style={{ fontSize: "0.75rem", color: "#22c55e", marginBottom: 8 }}>
                    ✦ Fully ingested — the original ZIM file is no longer required for reading.
                  </div>
                )}

                {/* Category tags */}
                {archive.categories?.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
                    {archive.categories.map(c => (
                      <span key={c.id} style={{ fontSize: "0.7rem", background: "var(--bg-active)", color: "var(--primary)", border: "1px solid var(--border-focus)", borderRadius: 10, padding: "1px 7px", fontWeight: 500 }}>
                        {c.name}
                      </span>
                    ))}
                  </div>
                )}

                {/* Action buttons */}
                <div style={{ display: "flex", gap: 6, justifyContent: "flex-end", flexWrap: "wrap" }}>
                  {archive.status === "idle" && (
                    <button className="btn btn-secondary btn-sm" style={{ color: "var(--primary)" }} onClick={() => startIndexing(archive.id)}>
                      <Icons.Play /> Index Now
                    </button>
                  )}
                  {(archive.status === "paused" || archive.status === "failed") && (
                    <button className="btn btn-secondary btn-sm" style={{ color: "var(--primary)" }} onClick={() => startIndexing(archive.id)}>
                      <Icons.Play /> Resume
                    </button>
                  )}
                  {archive.status === "indexing" && (
                    <>
                      <button className="btn btn-secondary btn-sm" style={{ color: "var(--warning)" }} onClick={() => pauseIndexing(archive.id)}>
                        <Icons.Pause /> Pause
                      </button>
                      <button className="btn btn-secondary btn-sm" style={{ color: "var(--danger)" }} onClick={() => cancelIndexing(archive.id)}>
                        <Icons.Close /> Cancel
                      </button>
                    </>
                  )}
                  {archive.status === "indexed" && (
                    <>
                      <span style={{ fontSize: "0.8rem", color: "var(--success)", fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
                        ✓ Ready to search
                      </span>
                      {!archive.is_extracted && (
                        <button
                          className="btn btn-secondary btn-sm"
                          style={{ color: "#a855f7" }}
                          onClick={() => extractArchive(archive.id)}
                          title="Extract all content so the ZIM file is no longer needed"
                        >
                          ↓ Extract Content
                        </button>
                      )}
                    </>
                  )}
                  {archive.status === "ready" && (
                    <span style={{ fontSize: "0.8rem", color: "#22c55e", fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
                      ✦ Fully ingested
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
