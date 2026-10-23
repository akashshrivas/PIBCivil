import Link from "next/link";
import { ArticleListItem } from "@/lib/types";
import BookmarkButton from "./BookmarkButton";

interface ArticleCardProps {
  article: ArticleListItem;
  // NEW: whether the logged-in user has saved this article.
  isSaved?: boolean;
  // NEW: the logged-in user's id, or null/undefined when logged out.
  userId?: string | null;
}

// Purely decorative -- there's no category field in the data to back
// this, so the icon color is just picked deterministically from the
// article's own id (same article always gets the same one).
const ICON_PALETTE = ["#6D5AE6", "#E8A33D", "#3DB88A", "#E05B8C", "#4C8CE0"];
const CHIP_PALETTE = ["chip-blue", "chip-orange"];

function hashToIndex(id: string, mod: number): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return hash % mod;
}

function formatDate(iso: string): string {
  return new Date(iso + "T00:00:00")
    .toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })
    .toUpperCase();
}

export default function ArticleCard({
  article,
  isSaved = false,
  userId = null,
}: ArticleCardProps) {
  const color = ICON_PALETTE[hashToIndex(article.id, ICON_PALETTE.length)];

  return (
    <Link href={`/articles/${article.id}`} className="article-card">
      <div className="article-card-top">
        <span className="article-date">{formatDate(article.published_on)}</span>
        {/* CHANGED: the decorative icon is now a working bookmark button */}
        <BookmarkButton
          articleId={article.id}
          initialSaved={isSaved}
          userId={userId}
        />
      </div>

      <div className="article-icon" style={{ background: `${color}22`, color }} aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6" />
        </svg>
      </div>

      <div className="article-body">
        <h2 className="article-title">{article.title}</h2>
        {article.ministry && (
          <div className="article-ministry">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 21h18" />
              <path d="M5 21V7l7-4 7 4v14" />
            </svg>
            {article.ministry}
          </div>
        )}
        {article.summary_preview && (
          <p className="article-preview">{article.summary_preview}</p>
        )}
      </div>

      {article.keywords.length > 0 && (
        <div className="chip-row">
          {article.keywords.map((kw, i) => (
            <span key={kw} className={`keyword-chip ${CHIP_PALETTE[i % CHIP_PALETTE.length]}`}>
              {kw}
            </span>
          ))}
        </div>
      )}

      <div className="article-footer">
        <span className="article-read-link">
          Read summary
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </span>
      </div>
    </Link>
  );
}
