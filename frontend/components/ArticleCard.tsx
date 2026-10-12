import Link from "next/link";
import { ArticleListItem } from "@/lib/types";

interface ArticleCardProps {
  article: ArticleListItem;
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

export default function ArticleCard({ article }: ArticleCardProps) {
  const color = ICON_PALETTE[hashToIndex(article.id, ICON_PALETTE.length)];

  return (
    <Link href={`/articles/${article.id}`} className="article-card">
      <div className="article-card-top">
        <span className="article-date">{formatDate(article.published_on)}</span>
        {/* Bookmarking needs real user auth -- not wired yet, shown for layout only */}
        <span className="article-save" aria-hidden="true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
          </svg>
        </span>
      </div>

      <div className="article-icon" style={{ background: `${color}22`, color }} aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6" />
        </svg>
      </div>

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
