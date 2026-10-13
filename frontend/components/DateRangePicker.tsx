"use client";

import { useEffect, useRef, useState } from "react";
import {
  addDays,
  addMonths,
  formatDisplayDate,
  getMonthGrid,
  isBetween,
  isSameDay,
  MONTH_NAMES,
  parseISODate,
  toISODate,
  WEEKDAY_LABELS,
} from "@/lib/dates";

interface DateRangePickerProps {
  after: string; // ISO date or ""
  before: string; // ISO date or ""
  onChange: (after: string, before: string) => void;
}

const PRESETS = [
  { label: "± 1 day", days: 1 },
  { label: "± 2 days", days: 2 },
  { label: "± 3 days", days: 3 },
  { label: "± 7 days", days: 7 },
  { label: "± 14 days", days: 14 },
];

export default function DateRangePicker({ after, before, onChange }: DateRangePickerProps) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"dates" | "flexible">("dates");
  const [viewMonth, setViewMonth] = useState(() => {
    const anchor = after ? parseISODate(after) : new Date();
    return new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  });
  const [draftStart, setDraftStart] = useState<Date | null>(after ? parseISODate(after) : null);
  const [draftEnd, setDraftEnd] = useState<Date | null>(before ? parseISODate(before) : null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click.
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function openPicker() {
    // Re-sync drafts with whatever the URL currently has, each time it opens.
    setDraftStart(after ? parseISODate(after) : null);
    setDraftEnd(before ? parseISODate(before) : null);
    setTab("dates");
    setOpen(true);
  }

  function handleDayClick(day: Date) {
    if (!draftStart || (draftStart && draftEnd)) {
      setDraftStart(day);
      setDraftEnd(null);
      return;
    }
    // Second click: finalize the range (swap if clicked before the start).
    const start = day < draftStart ? day : draftStart;
    const end = day < draftStart ? draftStart : day;
    setDraftStart(start);
    setDraftEnd(end);
    onChange(toISODate(start), toISODate(end));
    setOpen(false);
  }

  function handlePreset(days: number) {
    const today = new Date();
    const start = addDays(today, -days);
    const end = addDays(today, days);
    setDraftStart(start);
    setDraftEnd(end);
    onChange(toISODate(start), toISODate(end));
    setOpen(false);
  }

  function handleClear() {
    setDraftStart(null);
    setDraftEnd(null);
    onChange("", "");
    setOpen(false);
  }

  const label =
    after && before
      ? `${formatDisplayDate(parseISODate(after))} → ${formatDisplayDate(parseISODate(before))}`
      : "Add dates";

  const leftYear = viewMonth.getFullYear();
  const leftMonth = viewMonth.getMonth();
  const rightDate = addMonths(viewMonth, 1);

  return (
    <div className="date-picker" ref={containerRef}>
      <button type="button" className="filter-field" onClick={openPicker}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="4" width="18" height="18" rx="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
        <span>{label}</span>
      </button>

      {open && (
        <div className="date-picker-popover">
          <div className="date-picker-tabs">
            <button
              type="button"
              className={`date-picker-tab${tab === "dates" ? " active" : ""}`}
              onClick={() => setTab("dates")}
            >
              Dates
            </button>
            <button
              type="button"
              className={`date-picker-tab${tab === "flexible" ? " active" : ""}`}
              onClick={() => setTab("flexible")}
            >
              Flexible
            </button>
          </div>

          {tab === "dates" ? (
            <>
              <div className="date-picker-months">
                <button
                  type="button"
                  className="date-picker-nav"
                  onClick={() => setViewMonth(addMonths(viewMonth, -1))}
                  aria-label="Previous month"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="15 18 9 12 15 6" />
                  </svg>
                </button>

                <MonthCalendar
                  year={leftYear}
                  month={leftMonth}
                  draftStart={draftStart}
                  draftEnd={draftEnd}
                  onDayClick={handleDayClick}
                />
                <MonthCalendar
                  year={rightDate.getFullYear()}
                  month={rightDate.getMonth()}
                  draftStart={draftStart}
                  draftEnd={draftEnd}
                  onDayClick={handleDayClick}
                />

                <button
                  type="button"
                  className="date-picker-nav"
                  onClick={() => setViewMonth(addMonths(viewMonth, 1))}
                  aria-label="Next month"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </button>
              </div>
              <div className="date-picker-footer">
                <button type="button" className="date-picker-clear" onClick={handleClear}>
                  Clear dates
                </button>
              </div>
            </>
          ) : (
            <div className="date-picker-presets">
              <button type="button" className="chip" onClick={() => setTab("dates")}>
                Exact dates
              </button>
              {PRESETS.map((p) => (
                <button key={p.label} type="button" className="chip" onClick={() => handlePreset(p.days)}>
                  {p.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MonthCalendar({
  year,
  month,
  draftStart,
  draftEnd,
  onDayClick,
}: {
  year: number;
  month: number;
  draftStart: Date | null;
  draftEnd: Date | null;
  onDayClick: (d: Date) => void;
}) {
  const weeks = getMonthGrid(year, month);

  return (
    <div className="date-picker-month">
      <div className="date-picker-month-title">
        {MONTH_NAMES[month]} {year}
      </div>
      <div className="date-picker-weekdays">
        {WEEKDAY_LABELS.map((w, i) => (
          <span key={i}>{w}</span>
        ))}
      </div>
      <div className="date-picker-grid">
        {weeks.flatMap((week, wi) =>
          week.map((day, di) => {
            if (!day) return <span key={`${wi}-${di}`} />;

            const isStart = draftStart && isSameDay(day, draftStart);
            const isEnd = draftEnd && isSameDay(day, draftEnd);
            const inRange = draftStart && draftEnd && isBetween(day, draftStart, draftEnd);

            let cls = "date-picker-day";
            if (isStart || isEnd) cls += " selected";
            else if (inRange) cls += " in-range";

            return (
              <button
                key={`${wi}-${di}`}
                type="button"
                className={cls}
                onClick={() => onDayClick(day)}
              >
                {day.getDate()}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
