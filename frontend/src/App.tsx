import { useState, useEffect } from "react";
import { AppProvider, useAppContext } from "./context/AppContext";
import { ToastProvider } from "./components/Toast";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Sidebar } from "./components/Sidebar";
import { BrowserTabs } from "./components/BrowserTabs";
import { SearchPanel } from "./components/SearchPanel";
import { ArticleReader } from "./components/ArticleReader";
import { ArchiveManager } from "./components/ArchiveManager";
import { SettingsPanel } from "./components/SettingsPanel";
import { CommandPalette } from "./components/CommandPalette";
import { ChatSidebar } from "./components/ChatSidebar";

interface AppContentProps {
  activeView: string;
  setActiveView: (view: string) => void;
}

function AppContent({ activeView, setActiveView }: AppContentProps) {
  const { tabs } = useAppContext();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(() => {
    try { return localStorage.getItem("kiwi-chat-open") === "1"; } catch { return false; }
  });
  // Sidebar defaults to COLLAPSED on first launch — user can reopen any time
  // via the floating ☰ button (top-left) or Ctrl+B. Choice persists once set.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      const v = localStorage.getItem("kiwi-sidebar-collapsed");
      return v === null ? true : v === "1";
    } catch { return true; }
  });
  useEffect(() => {
    try { localStorage.setItem("kiwi-chat-open", chatOpen ? "1" : "0"); } catch {}
  }, [chatOpen]);
  useEffect(() => {
    try { localStorage.setItem("kiwi-sidebar-collapsed", sidebarCollapsed ? "1" : "0"); } catch {}
  }, [sidebarCollapsed]);

  useEffect(() => {
    if (activeView === "reader" && tabs.length === 0) {
      setActiveView("search");
    }
  }, [activeView, tabs.length, setActiveView]);

  // Global keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Ctrl+K / Cmd+K → open palette
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(o => !o);
        return;
      }
      // Ctrl+B → toggle the left navigation sidebar
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        setSidebarCollapsed(c => !c);
        return;
      }
      // "/" focuses the search bar from anywhere outside an input
      if (e.key === "/" && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        setActiveView("search");
        setTimeout(() => {
          const input = document.querySelector<HTMLInputElement>(".search-input-field");
          input?.focus();
        }, 50);
      }
    };

    // Listen for Ctrl+K bubbled up from the article iframe
    const onMessage = (e: MessageEvent) => {
      if (e.data && e.data.type === "kiwi-key" && e.data.key === "cmd-k") {
        setPaletteOpen(o => !o);
      }
    };

    window.addEventListener("keydown", onKey);
    window.addEventListener("message", onMessage);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("message", onMessage);
    };
  }, [setActiveView]);

  const containerCls = [
    "app-container",
    sidebarCollapsed ? "sidebar-collapsed" : "",
    chatOpen ? "chat-open" : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={containerCls}>
      {!sidebarCollapsed && (
        <Sidebar
          activeView={activeView}
          onNavigate={setActiveView}
          onToggleChat={() => setChatOpen(o => !o)}
          chatOpen={chatOpen}
          onCollapse={() => setSidebarCollapsed(true)}
        />
      )}
      {/* Floating reopener — shown only when the active view doesn't already
          host an inline hamburger (the reader puts one in its toolbar). */}
      {sidebarCollapsed && activeView !== "reader" && (
        <button
          className="sidebar-reopen-btn"
          onClick={() => setSidebarCollapsed(false)}
          title="Show navigation (Ctrl+B)"
          aria-label="Open sidebar"
        >
          ☰
        </button>
      )}
      <main className="workspace">
        <BrowserTabs onNavigate={setActiveView} />
        <ErrorBoundary>
          {activeView === "search" && (
            <SearchPanel
              onNavigate={setActiveView}
              onOpenChat={() => setChatOpen(true)}
            />
          )}
          {activeView === "reader" && (
            <ArticleReader
              onToggleChat={() => setChatOpen(o => !o)}
              chatOpen={chatOpen}
              sidebarCollapsed={sidebarCollapsed}
              onOpenSidebar={() => setSidebarCollapsed(false)}
            />
          )}
          {activeView === "archives" && <ArchiveManager onNavigate={setActiveView} />}
          {activeView === "settings" && <SettingsPanel />}
        </ErrorBoundary>
      </main>
      <ChatSidebar open={chatOpen} onClose={() => setChatOpen(false)} />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onNavigate={setActiveView}
      />
    </div>
  );
}

export default function App() {
  const [activeView, setActiveView] = useState("search");

  return (
    <ToastProvider>
      <AppProvider onNavigate={setActiveView}>
        <AppContent activeView={activeView} setActiveView={setActiveView} />
      </AppProvider>
    </ToastProvider>
  );
}
