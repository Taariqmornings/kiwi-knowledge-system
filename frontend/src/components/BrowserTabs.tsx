import { useAppContext } from "../context/AppContext";
import * as Icons from "./Icons";

export function BrowserTabs({ onNavigate }: { onNavigate: (view: string) => void }) {
  const { tabs, activeTabId, setActiveTabId, closeTab } = useAppContext();

  if (tabs.length === 0) return null;

  return (
    <div className="browser-tabs">
      {tabs.map(tab => (
        <div
          key={tab.id}
          className={`browser-tab ${activeTabId === tab.id ? "active" : ""}`}
          onClick={() => {
            setActiveTabId(tab.id);
            onNavigate("reader");
          }}
          onAuxClick={(e) => {
            // Middle-click closes a tab — standard browser convention
            if (e.button === 1) {
              e.preventDefault();
              closeTab(tab.id);
            }
          }}
          title={tab.title}
        >
          <span className="text-xs truncate flex-1">{tab.title}</span>
          <span
            className="close-tab-btn"
            onClick={(e) => { e.stopPropagation(); closeTab(tab.id); }}
            title="Close tab"
          >
            <Icons.Close />
          </span>
        </div>
      ))}
      <button
        className="browser-tab-new"
        title="New tab — go to search"
        onClick={() => {
          setActiveTabId(null);
          onNavigate("search");
        }}
      >
        <Icons.Plus />
      </button>
    </div>
  );
}
