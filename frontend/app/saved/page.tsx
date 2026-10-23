// frontend/app/saved/page.tsx
// ---------------------------------------------------------------
// "Saved" page: the logged-in user's bookmarked articles.
//
// It asks Supabase directly (not your FastAPI backend), because the
// request must carry the user's login. Your RLS policy on `bookmarks`
// then returns ONLY this user's rows.
// proxy.ts sends logged-out visitors to /login before they get here.
// ---------------------------------------------------------------
import Link from "next/link";
import { redirect } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import ArticleCard from "@/components/ArticleCard";
import MobileMenuButton from "@/components/MobileMenuButton";
import { createClient } from "@/lib/supabase/server";
import type { ArticleListItem } from "@/lib/types";

export const dynamic = "force-dynamic";

// The shape of what Supabase returns for our query below.
interface SummaryRow {
  summary: string;
  keywords: string[];
}
interface ArticleRow {
  id: string;
  release_id: string;
  title: string;
  ministry: string | null;
  published_on: string;
  url: string | null;
  article_summaries: SummaryRow[] | null;
}
interface BookmarkRow {
  created_at: string;
  // Depending on how Supabase describes the relation, it can arrive as one
  // object or a one-item list. We handle both below.
  articles: ArticleRow | ArticleRow[] | null;
}

export default async function SavedPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Safety net in case the proxy did not already redirect.
  if (!user) redirect("/login?next=/saved");

  // One request: this user's bookmarks, each with its article and summary.
  const { data, error } = await supabase
    .from("bookmarks")
    .select(
      "created_at, articles(id, release_id, title, ministry, published_on, url, article_summaries(summary, keywords))"
    )
    .order("created_at", { ascending: false });

  const rows = (data ?? []) as unknown as BookmarkRow[];

  // Convert each row into the same shape the home page cards use.
  const items: ArticleListItem[] = rows
    .map((row) => (Array.isArray(row.articles) ? row.articles[0] : row.articles))
    .filter((a): a is ArticleRow => !!a)
    .map((a) => {
      const summary = a.article_summaries?.[0];
      return {
        id: a.id,
        release_id: a.release_id,
        title: a.title,
        ministry: a.ministry,
        published_on: a.published_on,
        url: a.url,
        keywords: (summary?.keywords ?? []).slice(0, 3), // same cap as the backend
        summary_preview: summary?.summary ?? null,
      };
    });

  return (
    <div className="layout">
      <Sidebar active="saved" />

      <main className="main">
        <div className="topbar">
          <MobileMenuButton />
        </div>

        <h1 className="saved-title">Saved articles</h1>

        {error ? (
          <div className="empty-state">
            Couldn&apos;t load your saved articles. Please try again.
          </div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            You haven&apos;t saved anything yet. Tap the bookmark icon on an
            article to keep it here.{" "}
            <Link href="/" className="auth-link-button">
              Browse articles
            </Link>
          </div>
        ) : (
          <div className="card-grid">
            {items.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                isSaved
                userId={user.id}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
