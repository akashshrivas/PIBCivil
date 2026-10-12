import Link from "next/link";
import { notFound } from "next/navigation";
import { getArticle } from "@/lib/api";
import ArticleDetailContent from "@/components/ArticleDetailContent";

export const dynamic = "force-dynamic";

interface ArticlePageProps {
  params: Promise<{ id: string }>;
}

export default async function ArticlePage({ params }: ArticlePageProps) {
  const { id } = await params;

  let article;
  try {
    article = await getArticle(id);
  } catch {
    notFound();
  }

  return (
    <div className="layout">
      <main className="main" style={{ maxWidth: 760 }}>
        <Link
          href="/"
          className="search-field"
          style={{ display: "inline-flex", width: "auto", marginBottom: 20 }}
        >
          ← Back to Today&apos;s PIB
        </Link>

        <ArticleDetailContent article={article} />
      </main>
    </div>
  );
}
