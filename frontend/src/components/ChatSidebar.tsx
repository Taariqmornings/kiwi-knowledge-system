import { useCallback, useEffect, useRef, useState } from "react";
import { marked } from "marked";
import hljs from "highlight.js/lib/core";
import "highlight.js/styles/github-dark.css";
import { useAppContext } from "../context/AppContext";
import { api } from "../services/api";
import * as Icons from "./Icons";

// Register a focused subset of languages — importing the full highlight.js
// bundle pulls in every language and balloons the vendor chunk.
import javascript from "highlight.js/lib/languages/javascript";
import typescript from "highlight.js/lib/languages/typescript";
import python from "highlight.js/lib/languages/python";
import bash from "highlight.js/lib/languages/bash";
import json from "highlight.js/lib/languages/json";
import css from "highlight.js/lib/languages/css";
import xml from "highlight.js/lib/languages/xml";
import sql from "highlight.js/lib/languages/sql";
import markdown from "highlight.js/lib/languages/markdown";
import cpp from "highlight.js/lib/languages/cpp";
import java from "highlight.js/lib/languages/java";
import go from "highlight.js/lib/languages/go";
import rust from "highlight.js/lib/languages/rust";

hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("js", javascript);
hljs.registerLanguage("typescript", typescript);
hljs.registerLanguage("ts", typescript);
hljs.registerLanguage("python", python);
hljs.registerLanguage("py", python);
hljs.registerLanguage("bash", bash);
hljs.registerLanguage("shell", bash);
hljs.registerLanguage("json", json);
hljs.registerLanguage("css", css);
hljs.registerLanguage("xml", xml);
hljs.registerLanguage("html", xml);
hljs.registerLanguage("sql", sql);
hljs.registerLanguage("markdown", markdown);
hljs.registerLanguage("md", markdown);
hljs.registerLanguage("cpp", cpp);
hljs.registerLanguage("c++", cpp);
hljs.registerLanguage("java", java);
hljs.registerLanguage("go", go);
hljs.registerLanguage("rust", rust);

marked.setOptions({ gfm: true, breaks: true });
const markedRenderer = new marked.Renderer();
markedRenderer.code = (token: { text: string; lang?: string }) => {
  const lang = (token.lang || "").trim();
  let highlighted: string;
  try {
    if (lang && hljs.getLanguage(lang)) {
      highlighted = hljs.highlight(token.text, { language: lang, ignoreIllegals: true }).value;
    } else {
      highlighted = hljs.highlightAuto(token.text).value;
    }
  } catch {
    highlighted = escapeHtml(token.text);
  }
  const label = lang ? `<div class="chat-code-lang">${escapeHtml(lang)}</div>` : "";
  return `<div class="chat-code-block">${label}<pre><code class="hljs language-${escapeHtml(lang)}">${highlighted}</code></pre></div>`;
};

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] || c)
  );
}

interface Source {
  n: number;
  article_id: number;
  archive_id: string;
  title: string;
  archive_title: string;
  path: string;
}
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  status?: string;
  error?: string;
}
interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
}

const CONVS_KEY = "kiwi-chat-conversations";
const ACTIVE_KEY = "kiwi-chat-active-id";
const MAX_CONVS = 50;

const SAMPLE_QUERIES = [
  "What is photosynthesis?",
  "How does the immune system work?",
  "Explain the basics of binary search.",
];

// Cycling "thinking" messages — start with "Thinking…" then random.
const THINKING_PHRASES = [
  "Searching the archives…",
  "Reading sources…",
  "Cross-referencing…",
  "Synthesising…",
  "Reasoning…",
  "Manifesting wisdom…",
];

function newConversation(): Conversation {
  return { id: `c-${Date.now()}`, title: "New conversation", messages: [], createdAt: Date.now() };
}

function loadConvs(): Conversation[] {
  try {
    const raw = localStorage.getItem(CONVS_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw) as Conversation[];
    return Array.isArray(arr) ? arr : [];
  } catch { return []; }
}

export function ChatSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { openArticleInTab } = useAppContext();

  // ── Conversation store ─────────────────────────────────────────────
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    const existing = loadConvs();
    return existing.length ? existing : [newConversation()];
  });
  const [activeId, setActiveId] = useState<string>(() => {
    const stored = localStorage.getItem(ACTIVE_KEY);
    const list = loadConvs();
    if (stored && list.find(c => c.id === stored)) return stored;
    return list[0]?.id ?? "";
  });
  const [historyOpen, setHistoryOpen] = useState(false);

  const active = conversations.find(c => c.id === activeId) ?? conversations[0];

  // ── Critical: keep activeId in sync with the real conversation list ──
  // On first run the two `useState` initializers each call loadConvs()
  // independently, so a freshly-created conversation won't be in the
  // persisted list and activeId ends up "" — which would make every
  // updateActive() filter match zero rows and silently drop messages.
  // Resolved during render (React's derived-state pattern) so no effect
  // has to mutate state as a side effect.
  if (conversations.length > 0 && !conversations.some(c => c.id === activeId)) {
    setActiveId(conversations[0].id);
  }

  // Persist
  useEffect(() => {
    try {
      localStorage.setItem(CONVS_KEY, JSON.stringify(conversations.slice(0, MAX_CONVS)));
    } catch { /* quota / storage errors are non-fatal */ }
  }, [conversations]);
  useEffect(() => {
    try { if (activeId) localStorage.setItem(ACTIVE_KEY, activeId); } catch { /* non-fatal */ }
  }, [activeId]);

  // ── Streaming state ────────────────────────────────────────────────
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [thinking, setThinking] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll on new content
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [active?.messages, streaming, thinking]);

  // Auto-grow textarea up to 6 rows so long prompts are visible while typing
  useEffect(() => {
    const ta = inputRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    const lineHeight = 22;
    const maxRows = 6;
    const desired = Math.min(maxRows * lineHeight, ta.scrollHeight);
    ta.style.height = Math.max(2 * lineHeight, desired) + "px";
  }, [input]);

  // Focus when opened
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 80);
  }, [open]);

  // Esc closes
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Helper to mutate the active conversation. Falls back to mutating the
  // first conversation if activeId hasn't synced yet (e.g. very first send
  // after app launch when the sync effect hasn't fired).
  const updateActive = useCallback((fn: (c: Conversation) => Conversation) => {
    setConversations(prev => {
      if (prev.length === 0) return prev;
      const idx = prev.findIndex(c => c.id === activeId);
      const target = idx === -1 ? 0 : idx;
      const next = [...prev];
      next[target] = fn(next[target]);
      return next;
    });
  }, [activeId]);

  const startNewChat = useCallback(() => {
    const fresh = newConversation();
    setConversations(prev => [fresh, ...prev]);
    setActiveId(fresh.id);
    setHistoryOpen(false);
    setTimeout(() => inputRef.current?.focus(), 60);
  }, []);

  const deleteConversation = useCallback((id: string) => {
    setConversations(prev => {
      const next = prev.filter(c => c.id !== id);
      // Ensure we always have at least one conversation
      const safe = next.length ? next : [newConversation()];
      // If we deleted the active, switch to the most recent
      if (id === activeId) setActiveId(safe[0].id);
      return safe;
    });
  }, [activeId]);

  // ── Send message ───────────────────────────────────────────────────
  const sendQuestion = useCallback(async (question: string) => {
    if (!question.trim() || streaming || !active) return;

    // Capture history snapshot BEFORE we add the new user/assistant rows.
    // The backend caps and truncates further; we just ship the last 8 real
    // turns. Stripping errored / empty assistant slots keeps the prompt
    // focused and within Gemma's 2048-token context.
    const historySnapshot = (active.messages || [])
      .filter(m => !m.error && m.content && m.content.trim().length > 0)
      .slice(-8)
      .map(m => ({ role: m.role, content: m.content }));

    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: "user", content: question.trim() };
    const assistantId = `a-${Date.now()}`;
    const assistantMsg: ChatMessage = { id: assistantId, role: "assistant", content: "" };

    // Auto-title from first user message in this conversation
    updateActive(c => ({
      ...c,
      messages: [...c.messages, userMsg, assistantMsg],
      title: c.messages.length === 0 ? question.trim().slice(0, 60) : c.title,
    }));
    setInput("");
    setStreaming(true);
    setThinking("Thinking…");

    // Thinking animation: start with "Thinking…", then cycle random phrases every 3s
    let cycleTimer: ReturnType<typeof setTimeout> | null = null;
    const scheduleNext = (delay: number) => {
      cycleTimer = setTimeout(() => {
        const next = THINKING_PHRASES[Math.floor(Math.random() * THINKING_PHRASES.length)];
        setThinking(next);
        scheduleNext(3000);
      }, delay);
    };
    scheduleNext(3000);

    const stopThinking = () => {
      if (cycleTimer) clearTimeout(cycleTimer);
      setThinking(null);
    };

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const res = await api.askChat(
        { question: question.trim(), history: historySnapshot },
        ctrl.signal,
      );
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let firstTokenSeen = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let sep;
        while ((sep = buf.indexOf("\n\n")) !== -1) {
          const event = buf.slice(0, sep);
          buf = buf.slice(sep + 2);
          const lines = event.split("\n");
          let evtName = "message";
          let data = "";
          for (const line of lines) {
            if (line.startsWith("event:")) {
              evtName = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              // Per SSE spec, strip exactly ONE leading space after the
              // "data:" prefix — never trim, because the payload may itself
              // begin with significant whitespace (e.g. " The…").
              let payload = line.slice(5);
              if (payload.startsWith(" ")) payload = payload.slice(1);
              data = payload;
            }
          }
          if (!data) continue;
          if (evtName === "token") {
            if (!firstTokenSeen) { stopThinking(); firstTokenSeen = true; }
            // Tokens are always JSON-encoded strings from the backend — parse
            // to recover spaces/newlines verbatim.
            let piece = data;
            try {
              const parsed = JSON.parse(data);
              if (typeof parsed === "string") piece = parsed;
            } catch { /* not JSON — treat as raw text */ }
            updateActive(c => ({
              ...c,
              messages: c.messages.map(m =>
                m.id === assistantId ? { ...m, content: m.content + piece, status: undefined } : m
              ),
            }));
          } else if (evtName === "sources") {
            const parsed = JSON.parse(data) as { sources: Source[] };
            updateActive(c => ({
              ...c,
              messages: c.messages.map(m => m.id === assistantId ? { ...m, sources: parsed.sources } : m),
            }));
          } else if (evtName === "status") {
            const parsed = JSON.parse(data) as { message: string };
            updateActive(c => ({
              ...c,
              messages: c.messages.map(m => m.id === assistantId ? { ...m, status: parsed.message } : m),
            }));
          } else if (evtName === "error") {
            stopThinking();
            const parsed = JSON.parse(data) as { message: string };
            updateActive(c => ({
              ...c,
              messages: c.messages.map(m => m.id === assistantId ? { ...m, error: parsed.message } : m),
            }));
          }
        }
      }
    } catch (err) {
      if (!(err instanceof Error && err.name === "AbortError")) {
        const msg = err instanceof Error ? err.message : "Network error";
        updateActive(c => ({
          ...c,
          messages: c.messages.map(m => m.id === assistantId ? { ...m, error: msg } : m),
        }));
      }
    } finally {
      stopThinking();
      setStreaming(false);
      abortRef.current = null;
    }
  }, [streaming, active, updateActive]);

  const stopStreaming = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
  }, []);

  // Click handler for citation chips inserted inline by the markdown pipeline.
  // Uses event delegation so we can render the whole answer in a single
  // dangerouslySetInnerHTML — required because block elements like <p>, <ul>,
  // <h3> are not legal inside a <span> (browsers collapse the spacing).
  const onAnswerClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const target = (e.target as HTMLElement).closest(".chat-cite") as HTMLElement | null;
    if (!target) return;
    const n = parseInt(target.dataset.n || "", 10);
    const sources = (target.closest("[data-msg-id]") as HTMLElement | null)?.dataset.sources;
    if (!sources) return;
    try {
      const list: Source[] = JSON.parse(sources);
      const src = list.find(s => s.n === n);
      if (src) openArticleInTab(src.title, src.path, src.archive_id);
    } catch { /* malformed or missing source payload — ignore */ }
  }, [openArticleInTab]);

  // ── Render markdown answer with citation chips ─────────────────────
  const renderAnswer = (m: ChatMessage) => {
    if (!m.content && !m.status && !m.error) {
      return (
        <span className="chat-thinking">{thinking ?? "Thinking…"}</span>
      );
    }
    if (m.error) {
      return <span style={{ color: "var(--danger)" }}>⚠ {m.error}</span>;
    }
    // Replace [N] with an inline citation element BEFORE markdown parsing.
    // marked v12 preserves raw HTML by default, so the <sup> survives.
    const withChips = m.content.replace(
      /\[(\d+)\]/g,
      (_, n) => `<sup class="chat-cite" data-n="${n}" title="Source ${n}">${n}</sup>`
    );
    const html = marked.parse(withChips, { renderer: markedRenderer, async: false }) as string;
    return (
      <>
        <div
          className="chat-md"
          data-msg-id={m.id}
          data-sources={JSON.stringify(m.sources ?? [])}
          onClick={onAnswerClick}
          dangerouslySetInnerHTML={{ __html: html }}
        />
        {m.status && <div className="chat-status">{m.status}</div>}
      </>
    );
  };

  const messages = active?.messages ?? [];

  return (
    <aside className={`chat-sidebar${open ? " open" : ""}`}>
      <div className="chat-header">
        <div className="chat-title">
          <Icons.Sparkle /> <span>Ask Kiwi</span>
        </div>
        <div className="chat-header-actions">
          <button
            className="chat-icon-btn"
            onClick={() => setHistoryOpen(o => !o)}
            title="Chat history"
            aria-label="History"
          >
            <Icons.History />
          </button>
          <button
            className="chat-icon-btn"
            onClick={startNewChat}
            title="New chat"
            aria-label="New chat"
          >
            <Icons.Plus />
          </button>
          <button className="chat-icon-btn" onClick={onClose} title="Close (Esc)">
            <Icons.Close />
          </button>
        </div>
      </div>

      {historyOpen && (
        <div className="chat-history-panel">
          <div className="chat-history-header">Conversations · {conversations.length}</div>
          {conversations.length === 0 && (
            <div className="chat-history-empty">No saved chats yet.</div>
          )}
          {conversations.map(c => (
            <div
              key={c.id}
              className={`chat-history-item${c.id === activeId ? " active" : ""}`}
              onClick={() => { setActiveId(c.id); setHistoryOpen(false); }}
            >
              <div className="chat-history-title">{c.title || "Untitled chat"}</div>
              <div className="chat-history-meta">
                <span>{c.messages.filter(m => m.role === "user").length} q · {new Date(c.createdAt).toLocaleDateString()}</span>
                <button
                  className="chat-history-del"
                  onClick={(e) => { e.stopPropagation(); deleteConversation(c.id); }}
                  title="Delete"
                  aria-label="Delete conversation"
                >
                  ×
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="chat-empty">
            <Icons.Sparkle className="chat-empty-icon" />
            <div className="chat-empty-title">Ask anything from your archives</div>
            <div className="chat-empty-desc">
              Kiwi searches your indexed ZIM articles and answers with citations. Fully offline.
            </div>
            <div className="chat-samples">
              {SAMPLE_QUERIES.map((q, i) => (
                <button key={i} className="chat-sample" onClick={() => sendQuestion(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map(m => (
            <div key={m.id} className={`chat-msg chat-msg-${m.role}`}>
              <div className="chat-msg-body">
                {m.role === "user" ? m.content : renderAnswer(m)}
              </div>
              {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                <div className="chat-sources">
                  <div className="chat-sources-label">Sources</div>
                  {m.sources.map(s => (
                    <button
                      key={s.n}
                      className="chat-source-chip"
                      onClick={() => openArticleInTab(s.title, s.path, s.archive_id)}
                      title={s.archive_title}
                    >
                      <span className="chat-source-n">{s.n}</span>
                      <span className="chat-source-title">{s.title}</span>
                      <span className="chat-source-archive">{s.archive_title}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <div className="chat-input-row">
        <textarea
          ref={inputRef}
          className="chat-input"
          placeholder={streaming ? "Generating…" : "Ask a question…"}
          rows={2}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendQuestion(input);
            } else if (e.key === "Escape") {
              onClose();
            }
          }}
          disabled={streaming}
        />
        {streaming ? (
          <button className="chat-send" onClick={stopStreaming} title="Stop">■</button>
        ) : (
          <button
            className="chat-send"
            onClick={() => sendQuestion(input)}
            disabled={!input.trim()}
            title="Send (Enter)"
          >
            <Icons.Send />
          </button>
        )}
      </div>
    </aside>
  );
}
