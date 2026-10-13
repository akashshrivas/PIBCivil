// Mirrors backend/schemas/article.py and backend/schemas/common.py.
// Keep these in sync by hand -- there's no shared schema between the
// two projects yet, so a backend field rename won't show up here
// until you update it.

export interface ArticleListItem {
  id: string;
  release_id: string;
  title: string;
  ministry: string | null;
  published_on: string; // ISO date, e.g. "2026-10-03"
  url: string | null;
  keywords: string[];
  summary_preview: string | null;
}

export interface ArticleSummary {
  summary: string;
  important_facts: string[];
  keywords: string[];
  model: string;
  prompt_version: string;
}

export interface ArticleDetail extends ArticleListItem {
  summary: ArticleSummary | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
