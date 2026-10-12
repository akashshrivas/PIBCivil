import { ArticleDetail, Page, ArticleListItem } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export interface ArticleFilters {
  search?: string;
  ministry?: string;
  published_after?: string; // "YYYY-MM-DD"
  published_before?: string;
  order?: "newest" | "oldest";
  limit?: number;
  offset?: number;
}

/**
 * Builds a query string from only the filters that are actually set --
 * an empty search box shouldn't send "?search=" to the API.
 */
function toQueryString(filters: ArticleFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  return params.toString();
}

export async function getArticles(
  filters: ArticleFilters = {}
): Promise<Page<ArticleListItem>> {
  const query = toQueryString(filters);
  const res = await fetch(`${API_URL}/articles${query ? `?${query}` : ""}`, {
    // "Today's PIB" is time-sensitive -- don't let Next.js cache a stale page.
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to load articles (${res.status})`);
  }

  return res.json();
}

export async function getArticle(id: string): Promise<ArticleDetail> {
  const res = await fetch(`${API_URL}/articles/${id}`, { cache: "no-store" });

  if (res.status === 404) {
    throw new Error("Article not found");
  }
  if (!res.ok) {
    throw new Error(`Failed to load article (${res.status})`);
  }

  return res.json();
}

export async function getMinistries(): Promise<string[]> {
  const res = await fetch(`${API_URL}/articles/filters/ministries`, {
    // Ministry list changes rarely -- fine to cache for a while.
    next: { revalidate: 3600 },
  });

  if (!res.ok) {
    throw new Error(`Failed to load ministries (${res.status})`);
  }

  return res.json();
}
