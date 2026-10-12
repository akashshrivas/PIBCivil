interface HeroProps {
  total: number;
  dateLabel: string;
}

export default function Hero({ total, dateLabel }: HeroProps) {
  return (
    <div className="hero">
      <div className="hero-text">
        <div className="hero-eyebrow">TODAY&apos;S PIB</div>
        <h1 className="hero-headline">
          {total} new release{total === 1 ? "" : "s"}
        </h1>
        <div className="hero-sub">
          <span>Summarised for you</span>
          <span aria-hidden="true">&middot;</span>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="4" width="18" height="18" rx="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          <span>{dateLabel}</span>
        </div>
      </div>

      {/* Abstract column motif -- deliberately not a literal reproduction
          of the State Emblem, which carries its own usage restrictions. */}
      <svg className="hero-illustration" width="150" height="130" viewBox="0 0 150 130" aria-hidden="true">
        <circle cx="110" cy="55" r="48" fill="var(--accent)" opacity="0.12" />
        <rect x="60" y="30" width="14" height="70" rx="3" fill="var(--accent)" opacity="0.5" />
        <rect x="45" y="96" width="44" height="8" rx="2" fill="var(--accent)" opacity="0.6" />
        <rect x="38" y="106" width="58" height="9" rx="2" fill="var(--accent)" opacity="0.4" />
        <circle cx="67" cy="22" r="10" fill="var(--accent)" opacity="0.7" />
      </svg>

      <div className="hero-quote">
        <span className="hero-quote-bar" aria-hidden="true" />
        <span>&ldquo;Timely information for a more informed nation.&rdquo;</span>
      </div>
    </div>
  );
}
