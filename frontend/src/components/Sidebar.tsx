import { useAppContext } from "../context/AppContext";
import { VERSION } from "../version";
import * as Icons from "./Icons";

interface SidebarProps {
  activeView: string;
  onNavigate: (view: string) => void;
  onToggleChat?: () => void;
  chatOpen?: boolean;
  onCollapse?: () => void;
}

export function Sidebar({ activeView, onNavigate, onCollapse }: SidebarProps) {
  const { tabs, theme, toggleTheme } = useAppContext();

  return (
    <aside className="sidebar">
      <div className="brand-section" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-lg font-outfit shadow-md shadow-blue-500/20">
            K
          </div>
          <span className="brand-logo"><span style={{color:"#6b7280"}}>Ki</span><span style={{color:"#3b82f6"}}>wi</span></span>
        </div>
        {onCollapse && (
          <button
            className="sidebar-collapse-btn"
            onClick={onCollapse}
            title="Hide sidebar (Ctrl+B)"
            aria-label="Collapse sidebar"
          >
            ⟨
          </button>
        )}
      </div>

      <ul className="nav-list">
        <li>
          <div
            className={`nav-item ${activeView === "search" ? "active" : ""}`}
            onClick={() => { onNavigate("search"); }}
          >
            <span className="nav-icon"><Icons.Search /></span>
            <span>Search Engine</span>
          </div>
        </li>
        {tabs.length > 0 && (
          <li>
            <div
              className={`nav-item ${activeView === "reader" ? "active" : ""}`}
              onClick={() => onNavigate("reader")}
            >
              <span className="nav-icon"><Icons.Library /></span>
              <span>Active Reader ({tabs.length})</span>
            </div>
          </li>
        )}
        <li>
          <div
            className={`nav-item ${activeView === "archives" ? "active" : ""}`}
            onClick={() => onNavigate("archives")}
          >
            <span className="nav-icon"><Icons.Library /></span>
            <span>ZIM Archives</span>
          </div>
        </li>
        <li>
          <div
            className={`nav-item ${activeView === "settings" ? "active" : ""}`}
            onClick={() => onNavigate("settings")}
          >
            <span className="nav-icon"><Icons.Settings /></span>
            <span>Settings & Sync</span>
          </div>
        </li>
        {/* "Ask Kiwi" is reached from the search hero and the article
            toolbar — kept out of the sidebar nav per user preference. */}
      </ul>

      <div className="sidebar-footer">
        <div className="text-xs text-slate-500 font-medium">
          Kiwi v{VERSION}
        </div>
        <button className="btn btn-secondary btn-icon" onClick={toggleTheme} title="Toggle theme">
          {theme === "dark" ? <Icons.Sun /> : <Icons.Moon />}
        </button>
      </div>
    </aside>
  );
}
