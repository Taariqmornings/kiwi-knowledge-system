import { useState } from "react";
import { useReaderPrefs, type ColumnWidth, type ReaderTheme } from "../hooks/useReaderPrefs";

/**
 * Floating reading-mode control bar, bottom-right of the reader.
 * Lets the user adjust font size, column width, and theme without leaving the page.
 * Preferences persist via the `useReaderPrefs` hook.
 */
export function ReaderControls({ onPrint }: { onPrint?: () => void }) {
  const { prefs, setFontSize, setColumnWidth, setTheme } = useReaderPrefs();
  const [open, setOpen] = useState(false);

  const widths: { val: ColumnWidth; label: string }[] = [
    { val: "narrow", label: "Narrow" },
    { val: "normal", label: "Normal" },
    { val: "wide",   label: "Wide" },
  ];
  const themes: { val: ReaderTheme; label: string; bg: string; fg: string }[] = [
    { val: "light", label: "Light", bg: "#ffffff", fg: "#1f2328" },
    { val: "sepia", label: "Sepia", bg: "#f4ecd8", fg: "#5b4636" },
    { val: "dark",  label: "Dark",  bg: "#0d1117", fg: "#c9d1d9" },
  ];

  return (
    <div className="kiwi-reader-controls" style={{
      position: "fixed",
      right: 20,
      bottom: 20,
      zIndex: 200,
      display: "flex",
      flexDirection: "column",
      alignItems: "flex-end",
      gap: 10,
    }}>
      {open && (
        <div style={{
          background: "var(--bg-panel)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          boxShadow: "0 10px 30px rgba(0,0,0,.25)",
          padding: 14,
          width: 260,
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}>
          {/* Font size row */}
          <div>
            <div style={{ fontSize: ".72rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 6 }}>
              Font size · {prefs.fontSize}px
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setFontSize(prefs.fontSize - 1)} disabled={prefs.fontSize <= 12}>A−</button>
              <button className="btn btn-secondary btn-sm" onClick={() => setFontSize(16)}>Reset</button>
              <button className="btn btn-secondary btn-sm" onClick={() => setFontSize(prefs.fontSize + 1)} disabled={prefs.fontSize >= 22}>A+</button>
            </div>
          </div>

          {/* Column width row */}
          <div>
            <div style={{ fontSize: ".72rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 6 }}>
              Width
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              {widths.map(w => (
                <button
                  key={w.val}
                  className={`btn btn-sm ${prefs.columnWidth === w.val ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setColumnWidth(w.val)}
                  style={{ flex: 1 }}
                >
                  {w.label}
                </button>
              ))}
            </div>
          </div>

          {/* Theme row */}
          <div>
            <div style={{ fontSize: ".72rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 6 }}>
              Theme
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              {themes.map(t => (
                <button
                  key={t.val}
                  onClick={() => setTheme(t.val)}
                  title={t.label}
                  style={{
                    flex: 1,
                    background: t.bg,
                    color: t.fg,
                    border: prefs.theme === t.val ? "2px solid var(--primary)" : "1px solid var(--border)",
                    borderRadius: 6,
                    padding: "8px 6px",
                    cursor: "pointer",
                    fontSize: ".78rem",
                    fontWeight: 600,
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {onPrint && (
            <button className="btn btn-secondary btn-sm" onClick={onPrint}>🖨 Print article</button>
          )}
        </div>
      )}

      <button
        className="btn btn-primary"
        onClick={() => setOpen(o => !o)}
        title="Reading options"
        style={{ borderRadius: 999, width: 44, height: 44, padding: 0, fontSize: "1.1rem", boxShadow: "0 4px 12px rgba(0,0,0,.25)" }}
      >
        Aa
      </button>
    </div>
  );
}
