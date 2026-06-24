import type { Archive, Category, Suggestion, SearchResponse } from "../types";

declare global {
  interface Window {
    electronAPI?: {
      isElectron: boolean;
      platform: string;
      selectDirectory: () => Promise<string | null>;
      selectFiles: () => Promise<string[] | null>;
      getBackendUrl: () => Promise<string>;
      getBackendStatus: () => Promise<{ running: boolean }>;
      onBackendStatus: (callback: (status: { running: boolean; code?: number }) => void) => () => void;
    };
  }
}

const DEFAULT_BACKEND_HOST = "http://127.0.0.1:8000";
let backendHost: string | null = null;

async function getBackendHost(): Promise<string> {
  if (backendHost) return backendHost;
  if (window.electronAPI?.isElectron) {
    backendHost = await window.electronAPI.getBackendUrl();
  } else {
    backendHost = DEFAULT_BACKEND_HOST;
  }
  return backendHost;
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const host = await getBackendHost();
  const fullUrl = `${host}${url}`;

  // 30-second timeout — long enough to survive moments where the backend
  // is briefly busy from background indexing without false-failing the UI.
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  try {
    const res = await fetch(fullUrl, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(`API error ${res.status}: ${detail}`);
    }
    return await res.json();
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(`Request to ${fullUrl} timed out after 30s. Is the backend running?`);
    }
    if (err instanceof TypeError) {
      throw new Error(`Network error reaching ${fullUrl}: ${err.message}`);
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  // Archives
  getArchives: () => request<Archive[]>("/api/archives"),

  scanDirectory: (directory: string) =>
    request<Archive[]>("/api/archives/scan", {
      method: "POST",
      body: JSON.stringify({ directory }),
    }),

  addFiles: (files: string[]) =>
    request<Archive[]>("/api/archives/add-files", {
      method: "POST",
      body: JSON.stringify({ files }),
    }),

  deleteArchive: (archiveId: string) =>
    request<{ message: string }>(`/api/archives/${archiveId}`, {
      method: "DELETE",
    }),

  extractArchive: (archiveId: string) =>
    request<{ message: string }>(`/api/archives/${archiveId}/extract`, {
      method: "POST",
    }),

  cleanupStubs: () =>
    request<{ deleted: number; before: number; after: number; archives_touched: number }>(
      "/api/archives/cleanup-stubs", { method: "POST" }
    ),

  getHealth: () =>
    request<{
      articles: number;
      archives_by_status: Record<string, number>;
      db_size_mb: number;
      extracted_cache_mb: number;
      model_reachable: boolean;
      uptime_seconds: number;
      cpu_count: number;
      active_threads: number;
    }>("/api/health"),

  stopBackgroundWork: () =>
    request<{ paused_jobs: number }>("/api/health/stop-background-work", {
      method: "POST",
    }),

  getExtractionStatus: (archiveId: string) =>
    request<{ archive_id: string; extracted: number; total: number }>(
      `/api/archives/${archiveId}/extract/status`
    ),

  updateArchiveCategories: (archiveId: string, categoryIds: number[]) =>
    request<{ message: string }>(`/api/archives/${archiveId}/categories`, {
      method: "POST",
      body: JSON.stringify(categoryIds),
    }),

  // Indexing
  startIndexing: (archiveId: string) =>
    request<{ message: string }>(`/api/archives/${archiveId}/index/start`, {
      method: "POST",
    }),

  pauseIndexing: (archiveId: string) =>
    request<{ message: string }>(`/api/archives/${archiveId}/index/pause`, {
      method: "POST",
    }),

  cancelIndexing: (archiveId: string) =>
    request<{ message: string }>(`/api/archives/${archiveId}/index/cancel`, {
      method: "POST",
    }),

  getIndexStatus: (archiveId: string) =>
    request<{ status: string; progress: number; total: number }>(
      `/api/archives/${archiveId}/index/status`
    ),

  // Search
  search: (
    query: string,
    opts?: { archiveId?: string; categoryId?: number; page?: number; pageSize?: number }
  ) => {
    const params = new URLSearchParams({ q: query, page: String(opts?.page ?? 1), page_size: String(opts?.pageSize ?? 30) });
    if (opts?.archiveId) params.set("archive_id", opts.archiveId);
    if (opts?.categoryId) params.set("category_id", String(opts.categoryId));
    return request<SearchResponse>(`/api/search/query?${params}`);
  },

  autocomplete: (query: string, limit = 8) => {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    return request<{ suggestions: Suggestion[] }>(
      `/api/search/autocomplete?${params}`
    );
  },

  // Categories
  getCategories: () => request<Category[]>("/api/search/categories"),

  // App settings (persisted on backend, survives restarts)
  getSettings: () => request<{ zim_scan_path: string }>("/api/settings"),
  updateSettings: (data: { zim_scan_path: string }) =>
    request<{ zim_scan_path: string }>("/api/settings", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Categories — browse without a search query
  browseCategory: (categoryId: number, opts?: { page?: number; pageSize?: number }) => {
    const params = new URLSearchParams({
      page: String(opts?.page ?? 1),
      page_size: String(opts?.pageSize ?? 30),
    });
    return request<SearchResponse>(`/api/search/categories/${categoryId}/articles?${params}`);
  },

  // Browse ALL indexed articles regardless of category
  browseAllArticles: (opts?: { page?: number; pageSize?: number }) => {
    const params = new URLSearchParams({
      page: String(opts?.page ?? 1),
      page_size: String(opts?.pageSize ?? 30),
    });
    return request<SearchResponse>(`/api/search/all?${params}`);
  },

  // SSE stream for real-time indexing progress
  getIndexStream: async (archiveId: string): Promise<EventSource> => {
    const host = await getBackendHost();
    return new EventSource(`${host}/api/archives/${archiveId}/index/stream`);
  },

  // Articles
  getArticleUrl: async (
    archiveId: string,
    path: string,
    theme = "dark",
    opts?: { font?: number; width?: "narrow" | "normal" | "wide" }
  ) => {
    const host = await getBackendHost();
    const encodedPath = path.split("/").map(encodeURIComponent).join("/");
    const params = new URLSearchParams({ theme });
    if (opts?.font) params.set("font", String(opts.font));
    if (opts?.width) params.set("width", opts.width);
    return `${host}/api/articles/${archiveId}/view/${encodedPath}?${params}`;
  },

  randomArticle: (opts?: { archiveId?: string; categoryId?: number }) => {
    const params = new URLSearchParams();
    if (opts?.archiveId) params.set("archive_id", opts.archiveId);
    if (opts?.categoryId) params.set("category_id", String(opts.categoryId));
    return request<{
      id: number; archive_id: string; archive_title: string;
      title: string; path: string; summary: string; mimetype: string;
    }>(`/api/search/random?${params}`);
  },

  getMediaUrl: async (archiveId: string, path: string) => {
    const host = await getBackendHost();
    const encodedPath = path.split("/").map(encodeURIComponent).join("/");
    return `${host}/api/articles/${archiveId}/media/${encodedPath}`;
  },
};
