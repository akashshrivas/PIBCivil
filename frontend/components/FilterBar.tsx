"use client";

import { useRouter, useSearchParams } from "next/navigation";
import DateRangePicker from "./DateRangePicker";
import Dropdown from "./Dropdown";

interface FilterBarProps {
  ministries: string[];
  total: number;
}

const MINISTRY_ICON = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 21h18" />
    <path d="M5 21V7l7-4 7 4v14" />
  </svg>
);

const SORT_ICON = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 6h18M6 12h12M10 18h4" />
  </svg>
);

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

      <Dropdown
        icon={MINISTRY_ICON}
        value={activeMinistry}
        placeholder="Ministry"
        options={ministries.map((m) => ({ value: m, label: m }))}
        onChange={(v) => updateParam("ministry", v)}
      />

      <DateRangePicker
        after={after}
        before={before}
        onChange={(newAfter, newBefore) => {
          const params = new URLSearchParams(searchParams.toString());
          if (newAfter) params.set("published_after", newAfter);
          else params.delete("published_after");
          if (newBefore) params.set("published_before", newBefore);
          else params.delete("published_before");
          params.delete("offset");
          router.push(`/?${params.toString()}`);
        }}
      />

      <Dropdown
        icon={SORT_ICON}
        value={order}
        placeholder="Latest first"
        clearable={false}
        options={[
          { value: "newest", label: "Latest first" },
          { value: "oldest", label: "Oldest first" },
        ]}
        onChange={(v) => updateParam("order", v)}
      />

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
