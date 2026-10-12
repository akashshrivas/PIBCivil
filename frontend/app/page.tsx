import { Suspense } from "react";
import Sidebar from "@/components/Sidebar";
import SearchBar from "@/components/SearchBar";
import FilterBar from "@/components/FilterBar";
import Hero from "@/components/Hero";
import ArticleCard from "@/components/ArticleCard";
import { getArticles, getMinistries } from "@/lib/api";

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
              <ArticleCard key={article.id} article={article} />
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
