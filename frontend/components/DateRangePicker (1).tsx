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
  after: string; // start date as "YYYY-MM-DD", or "" if none
  before: string; // end date as "YYYY-MM-DD", or "" if none
  onChange: (after: string, before: string) => void; // tells the parent the new range
}

// The "Flexible" tab buttons: ± N days around today.
const PRESETS = [
  { label: "± 1 day", days: 1 },
  { label: "± 2 days", days: 2 },
  { label: "± 3 days", days: 3 },
  { label: "± 7 days", days: 7 },
  { label: "± 14 days", days: 14 },
];

export default function DateRangePicker({ after, before, onChange }: DateRangePickerProps) {
  // Is the popup open or closed?
  const [open, setOpen] = useState(false);
  // Which tab is showing: exact dates or flexible presets.
  const [tab, setTab] = useState<"dates" | "flexible">("dates");

  // The month currently shown. We store the 1st of that month.
  // It starts at the selected start date's month, or today's month if nothing is selected.
  const [viewMonth, setViewMonth] = useState(() => {
    const anchor = after ? parseISODate(after) : new Date();
    return new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  });

  // "Draft" dates: what the user is picking right now, before the range is finished.
  const [draftStart, setDraftStart] = useState<Date | null>(after ? parseISODate(after) : null);
  const [draftEnd, setDraftEnd] = useState<Date | null>(before ? parseISODate(before) : null);

  // A reference to the outer <div>, used to detect clicks outside it.
  const containerRef = useRef<HTMLDivElement>(null);

  // Close the popup when the user taps outside it, or presses Escape.
  useEffect(() => {
    // "pointerdown" works for mouse, touch and pen, so it is better on phones.
    function onPointerDown(e: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    // Cleanup: remove the listeners when the component goes away.
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  // Stop the page behind the bottom sheet from scrolling while it is open (mobile only).
  useEffect(() => {
    if (!open) return;
    const isMobile = window.matchMedia("(max-width: 640px)").matches;
    if (!isMobile) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous; // restore on close
    };
  }, [open]);

  function openPicker() {
    // Re-sync drafts with the current filter values every time it opens.
    setDraftStart(after ? parseISODate(after) : null);
    setDraftEnd(before ? parseISODate(before) : null);
    // Jump the calendar to the month of the selected start date.
    const anchor = after ? parseISODate(after) : new Date();
    setViewMonth(new Date(anchor.getFullYear(), anchor.getMonth(), 1));
    setTab("dates");
    setOpen(true);
  }

  function handleDayClick(day: Date) {
    // First click (or starting over): remember the start, clear the end.
    if (!draftStart || (draftStart && draftEnd)) {
      setDraftStart(day);
      setDraftEnd(null);
      return;
    }
    // Second click: finish the range. If the user clicked a day BEFORE
    // the start, swap them so start is always the earlier date.
    const start = day < draftStart ? day : draftStart;
    const end = day < draftStart ? draftStart : day;
    setDraftStart(start);
    setDraftEnd(end);
    onChange(toISODate(start), toISODate(end)); // tell the parent
    setOpen(false);
  }

  function handlePreset(days: number) {
    const today = new Date();
    const start = addDays(today, -days); // N days before today
    const end = addDays(today, days); // N days after today
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

  // Text shown on the button.
  const label =
    after && before
      ? `${formatDisplayDate(parseISODate(after))} → ${formatDisplayDate(parseISODate(before))}`
      : "Add dates";

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
        <>
          {/* Dark overlay behind the bottom sheet. Only visible on mobile (see globals.css). */}
          <div className="date-picker-backdrop" onClick={() => setOpen(false)} />

          <div className="date-picker-popover" role="dialog" aria-label="Choose dates">
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
                {/* Header row: [<]  June 2026  [>] */}
                <div className="date-picker-header">
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

                  <div className="date-picker-month-title">
                    {MONTH_NAMES[viewMonth.getMonth()]} {viewMonth.getFullYear()}
                  </div>

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

                {/* Only ONE month is rendered now. */}
                <MonthCalendar
                  year={viewMonth.getFullYear()}
                  month={viewMonth.getMonth()}
                  draftStart={draftStart}
                  draftEnd={draftEnd}
                  onDayClick={handleDayClick}
                />

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
        </>
      )}
    </div>
  );
}

// Draws the weekday row and the grid of days for ONE month.
// (The month title now lives in the header above, so it is not repeated here.)
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
  // getMonthGrid returns weeks; each week is 7 entries, with null for empty cells.
  const weeks = getMonthGrid(year, month);

  return (
    <div className="date-picker-month">
      <div className="date-picker-weekdays">
        {WEEKDAY_LABELS.map((w, i) => (
          <span key={i}>{w}</span>
        ))}
      </div>
      <div className="date-picker-grid">
        {weeks.flatMap((week, wi) =>
          week.map((day, di) => {
            // Empty cell (days from the previous/next month): keeps the grid aligned.
            if (!day) return <span key={`${wi}-${di}`} />;

            const isStart = draftStart && isSameDay(day, draftStart);
            const isEnd = draftEnd && isSameDay(day, draftEnd);
            const inRange = draftStart && draftEnd && isBetween(day, draftStart, draftEnd);

            // Build the CSS class: "selected" for the two ends, "in-range" for days between.
            let cls = "date-picker-day";
            if (isStart || isEnd) cls += " selected";
            else if (inRange) cls += " in-range";

            return (
              <button key={`${wi}-${di}`} type="button" className={cls} onClick={() => onDayClick(day)}>
                {day.getDate()}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
