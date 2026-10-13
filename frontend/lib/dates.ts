// Small date helpers, deliberately hand-rolled (no date library) --
// the only operations needed are month-grid building, ISO formatting,
// and day arithmetic, which plain Date covers without adding a dependency.

export function toISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function parseISODate(s: string): Date {
  // Appending T00:00:00 forces local-time parsing instead of UTC, so
  // the date shown always matches the date actually stored/selected.
  return new Date(s + "T00:00:00");
}

export function formatDisplayDate(d: Date): string {
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function addDays(d: Date, n: number): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
}

export function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function isBetween(d: Date, start: Date, end: Date): boolean {
  return d.getTime() > start.getTime() && d.getTime() < end.getTime();
}

export type MonthGrid = (Date | null)[][];

/** 6 rows x 7 columns (Sun-Sat), null for the leading/trailing blanks. */
export function getMonthGrid(year: number, month: number): MonthGrid {
  const firstDay = new Date(year, month, 1);
  const startWeekday = firstDay.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells: (Date | null)[] = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
  while (cells.length % 7 !== 0) cells.push(null);

  const weeks: MonthGrid = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}

export const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export const WEEKDAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];
