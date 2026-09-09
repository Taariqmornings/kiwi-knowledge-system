import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, getBackendHost } from "./api";

describe("getBackendHost", () => {
  it("returns the default localhost backend in browser mode", async () => {
    expect(window.electronAPI).toBeUndefined();
    expect(await getBackendHost()).toBe("http://127.0.0.1:8000");
  });

  it("caches the resolved host across calls", async () => {
    const first = await getBackendHost();
    const second = await getBackendHost();
    expect(first).toBe(second);
  });
});

describe("api client", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    mockFetch.mockReset();
  });

  function okJson(body: unknown) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(body),
    } as Response);
  }

  it("builds the search query URL with pagination params", async () => {
    mockFetch.mockImplementation(() =>
      okJson({ results: [], total_count: 0, page: 1, page_size: 30, total_pages: 1, has_next: false, has_previous: false })
    );

    await api.search("python programming", { page: 2, pageSize: 30 });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/search/query?");
    expect(url).toContain("q=python+programming");
    expect(url).toContain("page=2");
    expect(url).toContain("page_size=30");
    expect(url.startsWith("http://127.0.0.1:8000")).toBe(true);
    expect(init.method ?? "GET").toBe("GET");
  });

  it("POSTs to the chat endpoint with question and history", async () => {
    mockFetch.mockImplementation(() => okJson({}));

    const res = await api.askChat({
      question: "What is photosynthesis?",
      history: [{ role: "user", content: "Hi" }],
    });

    expect(res).toBeDefined();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/chat/ask");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      question: "What is photosynthesis?",
      history: [{ role: "user", content: "Hi" }],
    });
  });

  it("builds article view URLs with percent-encoded paths", async () => {
    const url = await api.getArticleUrl("abc123", "A/Physics/Quantum.html", "dark");
    expect(url).toBe(
      "http://127.0.0.1:8000/api/articles/abc123/view/A/Physics/Quantum.html?theme=dark"
    );
  });
});