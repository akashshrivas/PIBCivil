"use client";

import { useRouter, useSearchParams } from "next/navigation";

interface FilterBarProps {
  ministries: string[];
  total: number;
}

export default function FilterBar({ ministries, total }: FilterBarProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeMinistry = searchParams.get("ministry") ?? "";
  const after = searchParams.get("published_after") ?? "";
  const before = searchParams.get("published_before") ?? "";
  const order = searchParams.get("order") ?? "newest";
  const hasAnyFilter = activeMinistry || after || before || searchParams.get("search");

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    if (key !== "order") {
      params.delete("offset");
    }
    router.push(`/?${params.toString()}`);
  }

  function clearAll() {
    router.push("/");
  }

  return (
    <div className="filter-bar">
      <button type="button" className="chip active">
        All ({total})
      </button>

      <label className="filter-field filter-field-ministry">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 21h18" />
          <path d="M5 21V7l7-4 7 4v14" />
        </svg>
        <select
          value={activeMinistry}
          onChange={(e) => updateParam("ministry", e.target.value)}
          aria-label="Filter by ministry"
        >
          <option value="">Ministry</option>
          {ministries.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>

      <label className="filter-field filter-field-range">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="4" width="18" height="18" rx="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
        <input
          type="date"
          value={after}
          onChange={(e) => updateParam("published_after", e.target.value)}
          aria-label="From date"
        />
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <line x1="5" y1="12" x2="19" y2="12" />
          <polyline points="12 5 19 12 12 19" />
        </svg>
        <input
          type="date"
          value={before}
          onChange={(e) => updateParam("published_before", e.target.value)}
          aria-label="To date"
        />
      </label>

      <label className="filter-field">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 6h18M6 12h12M10 18h4" />
        </svg>
        <select
          value={order}
          onChange={(e) => updateParam("order", e.target.value)}
          aria-label="Sort order"
        >
          <option value="newest">Latest first</option>
          <option value="oldest">Oldest first</option>
        </select>
      </label>

      <button
        type="button"
        className="filter-field filter-clear"
        onClick={clearAll}
        disabled={!hasAnyFilter}
        style={{ marginLeft: "auto" }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="1 4 1 10 7 10" />
          <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
        </svg>
        Clear filters
      </button>
    </div>
  );
}
