"use client";

import { useEffect, useRef, useState } from "react";
import {
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
// NOTE: addDays is no longer imported, because the "Flexible"
// presets (± N days) were removed.

interface DateRangePickerProps {
  after: string; // start date as "YYYY-MM-DD", or "" if none
  before: string; // end date as "YYYY-MM-DD", or "" if none
  onChange: (after: string, before: string) => void; // tells the parent the new dates
}

// The two modes the popup can be in:
//   "date"  -> pick ONE particular day
//   "range" -> pick a start day and an end day
type Mode = "date" | "range";

export default function DateRangePicker({ after, before, onChange }: DateRangePickerProps) {
  // Is the popup open or closed?
  const [open, setOpen] = useState(false);

  // NEW: which tab is showing. It replaces the old "dates / flexible" tab.
  // If the page loads with a real range (start and end are different
  // days) we start in "range" mode, otherwise in "date" mode.
  const [mode, setMode] = useState<Mode>(
    after && before && after !== before ? "range" : "date"
  );

  // The month currently shown. We store the 1st of that month.
  // It starts at the selected start date's month, or today's month if nothing is selected.
  const [viewMonth, setViewMonth] = useState(() => {
    const anchor = after ? parseISODate(after) : new Date();
    return new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  });

  // "Draft" dates: what the user is picking right now, before it is applied.
  // In "date" mode both drafts hold the same day.
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

  // Stop the page behind the bottom sheet from scrolling while it is open (mobile).
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
    // NEW: reopen in the mode that matches what is currently selected.
    setMode(after && before && after !== before ? "range" : "date");
    setOpen(true);
  }

  // NEW: called when the user clicks the "Date" or "Range" tab.
  function switchMode(next: Mode) {
    if (next === mode) return;
    setMode(next);
    // Clear the half-finished picking so a single day is never
    // mistaken for the start of a range. We do NOT call onChange here,
    // so the results list stays as it is until a new day is picked.
    setDraftStart(null);
    setDraftEnd(null);
  }

  function handleDayClick(day: Date) {
    // NEW: "date" mode. One click picks the day: start and end are
    // the same day, which is how a single day is stored in the URL.
    if (mode === "date") {
      setDraftStart(day);
      setDraftEnd(day);
      onChange(toISODate(day), toISODate(day)); // tell the parent
      setOpen(false);
      return;
    }

    // "range" mode (unchanged from before).
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

  function handleClear() {
    setDraftStart(null);
    setDraftEnd(null);
    onChange("", "");
    setOpen(false);
  }

  // Text shown on the button.
  // NEW: if start and end are the same day, show just that one day.
  let label = "Add dates";
  if (after && before) {
    label =
      after === before
        ? formatDisplayDate(parseISODate(after))
        : `${formatDisplayDate(parseISODate(after))} → ${formatDisplayDate(parseISODate(before))}`;
  }

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
          {/* Dark overlay behind the bottom sheet. Only visible on mobile (see CSS). */}
          <div className="date-picker-backdrop" onClick={() => setOpen(false)} />

          <div className="date-picker-popover" role="dialog" aria-label="Choose dates">
            {/* The two tabs. They reuse your existing tab classes,
                so they look exactly like the old "Dates / Flexible" tabs. */}
            <div className="date-picker-tabs">
              <button
                type="button"
                className={`date-picker-tab${mode === "date" ? " active" : ""}`}
                onClick={() => switchMode("date")}
              >
                Date
              </button>
              <button
                type="button"
                className={`date-picker-tab${mode === "range" ? " active" : ""}`}
                onClick={() => switchMode("range")}
              >
                Range
              </button>
            </div>

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

            {/* Only ONE month is rendered. It is the same calendar in both modes;
                only what a click does (see handleDayClick) is different. */}
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
          </div>
        </>
      )}
    </div>
  );
}

// Draws the weekday row and the grid of days for ONE month.
// (Unchanged from your version.)
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
