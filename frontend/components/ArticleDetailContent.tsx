import { ArticleDetail } from "@/lib/types";

export default function ArticleDetailContent({ article }: { article: ArticleDetail }) {
  return (
    <>
      {article.ministry && (
        <div style={{ marginBottom: 6, fontSize: 13, color: "var(--text-muted)" }}>
          {article.ministry} · {article.published_on}
        </div>
      )}

      <h1 style={{ fontSize: 26, fontWeight: 800, margin: "0 0 18px", lineHeight: 1.3 }}>
        {article.title}
      </h1>

      {article.summary ? (
        <>
          <p style={{ fontSize: 15, lineHeight: 1.6, color: "var(--text-muted)" }}>
            {article.summary.summary}
          </p>

          {article.summary.important_facts.length > 0 && (
            <>
              <div style={{ fontSize: 14, fontWeight: 700, margin: "18px 0 8px" }}>
                Important points
              </div>
              <ul style={{ fontSize: 14, lineHeight: 1.8, color: "var(--text-muted)", paddingLeft: 20 }}>
                {article.summary.important_facts.map((fact, i) => (
                  <li key={i}>{fact}</li>
                ))}
              </ul>
            </>
          )}

          {article.summary.keywords.length > 0 && (
            <div className="chip-row" style={{ marginTop: 16 }}>
              {article.summary.keywords.map((kw) => (
                <span key={kw} className="keyword-chip">
                  {kw}
                </span>
              ))}
            </div>
          )}
        </>
      ) : (
        <p style={{ color: "var(--text-muted)" }}>No summary available for this article yet.</p>
      )}

      {article.url && (
        <p style={{ marginTop: 24 }}>
          <a href={article.url} target="_blank" rel="noreferrer">
            View original PIB release →
          </a>
        </p>
      )}
    </>
  );
}
