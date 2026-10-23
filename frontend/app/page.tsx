import { Suspense } from "react";
import Sidebar from "@/components/Sidebar";
import SearchBar from "@/components/SearchBar";
import FilterBar from "@/components/FilterBar";
import Hero from "@/components/Hero";
import ArticleCard from "@/components/ArticleCard";
import MobileMenuButton from "@/components/MobileMenuButton"; // NEW: hamburger button for phones
import { getArticles, getMinistries } from "@/lib/api";
import { createClient } from "@/lib/supabase/server"; // NEW: to know who is logged in

export const dynamic = "force-dynamic";

const PAGE_SIZE = 9;

interface HomeProps {
  searchParams: Promise<{ [key: string]: string | undefined }>;
}

export default async function Home({ searchParams: searchParamsPromise }: HomeProps) {
  const searchParams = await searchParamsPromise;
  const offset = Number(searchParams.offset ?? 0);
  const order = searchParams.order === "oldest" ? "oldest" : "newest";

  const filters = {
    search: searchParams.search,
    ministry: searchParams.ministry,
    published_after: searchParams.published_after,
    published_before: searchParams.published_before,
    order: order as "newest" | "oldest",
    limit: PAGE_SIZE,
    offset,
  };

  const [page, ministries] = await Promise.all([
    getArticles(filters),
    getMinistries(),
  ]);

  // NEW: find out who is logged in, and which of the articles on this
  // page they have already saved. RLS makes the bookmarks query return
  // only the current user's rows, so no extra user filter is needed.
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  let savedIds = new Set<string>();
  if (user && page.items.length > 0) {
    const { data: saved } = await supabase
      .from("bookmarks")
      .select("article_id")
      .in("article_id", page.items.map((a) => a.id));
    savedIds = new Set((saved ?? []).map((row) => row.article_id as string));
  }

  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < page.total;

  function pageUrl(newOffset: number) {
    const params = new URLSearchParams(
      Object.entries(searchParams).filter(([, v]) => v) as [string, string][]
    );
    params.set("offset", String(newOffset));
    return `/?${params.toString()}`;
  }

  const todayLabel = new Date().toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });

  return (
    <div className="layout">
      <Sidebar />

      <main className="main">
        <div className="topbar">
          {/* NEW: hamburger button. Hidden on desktop, visible on screens 900px wide or narrower. */}
          <MobileMenuButton />

          <Suspense fallback={<div className="search-field">Loading search…</div>}>
            <SearchBar />
          </Suspense>
        </div>

        <Hero total={page.total} dateLabel={todayLabel} />

        <Suspense fallback={<div className="filter-bar" />}>
          <FilterBar ministries={ministries} total={page.total} />
        </Suspense>

        {page.items.length === 0 ? (
          <div className="empty-state">
            No articles match these filters. Try clearing one of them.
          </div>
        ) : (
          <div className="card-grid">
            {page.items.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                isSaved={savedIds.has(article.id)} // NEW
                userId={user?.id ?? null} // NEW
              />
            ))}
          </div>
        )}

        <div className="pagination">
          {hasPrev ? (
            <a href={pageUrl(Math.max(0, offset - PAGE_SIZE))}>Previous</a>
          ) : (
            <span className="disabled">Previous</span>
          )}
          {hasNext ? (
            <a href={pageUrl(offset + PAGE_SIZE)}>Next</a>
          ) : (
            <span className="disabled">Next</span>
          )}
        </div>
      </main>
    </div>
  );
}
