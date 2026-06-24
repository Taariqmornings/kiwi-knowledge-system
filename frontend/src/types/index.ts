export interface Category {
  id: number;
  name: string;
  icon: string;
}

export interface Archive {
  id: string;
  name: string;
  path: string;
  title?: string;
  description?: string;
  creator?: string;
  date?: string;
  language?: string;
  size_bytes: number;
  article_count: number;
  status: string;
  indexed_count: number;
  is_extracted: boolean;
  created_at: string;
  categories: Category[];
}

export interface Article {
  id: number;
  archive_id: string;
  archive_title?: string;
  title: string;
  path: string;
  summary?: string;
  keywords?: string;
  mimetype: string;
  score?: number;
  title_highlight?: string;
  snippet?: string;
}

export interface SearchResponse {
  results: Article[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface Suggestion {
  title: string;
  path: string;
  archive_id: string;
  archive_title: string;
}

export interface TabHistoryEntry {
  path: string;
  archiveId: string;
  title: string;
  /** Last known scroll position as a fraction 0..1; restored on back/forward. */
  scrollPercent?: number;
}

export interface Tab {
  id: string;
  title: string;
  path: string;
  archiveId: string;
  /**
   * Per-tab navigation stack. Each entry carries archiveId so back/forward
   * can move across archives (e.g. clicking a link in archive A that points
   * to archive B → new tab whose back arrow returns to the A article).
   */
  history: TabHistoryEntry[];
  historyIndex: number;
}

export interface Bookmark {
  id: string;
  title: string;
  path: string;
  archiveId: string;
}
