"use client";

// components/SingleDatePicker.tsx
// ---------------------------------------------------------------
// Picks ONE particular day.
//
// It uses the browser's built-in date input, so there is no extra
// library to install. It reuses your existing "filter-field" CSS
// class, so it should look like the other controls in the filter bar.
// ---------------------------------------------------------------

interface SingleDatePickerProps {
  // The currently selected day as "YYYY-MM-DD", or "" if none.
  // This is the same format your URL params already use.
  value: string;
  // Called with the new day ("YYYY-MM-DD"), or "" when it is cleared.
  onChange: (value: string) => void;
}

export default function SingleDatePicker({
  value,
  onChange,
}: SingleDatePickerProps) {
  return (
    <input
      type="date"
      className="filter-field"
      value={value}
      // The browser already gives us the value as "YYYY-MM-DD",
      // so we can pass it straight to the parent with no conversion.
      onChange={(e) => onChange(e.target.value)}
      aria-label="Pick a date"
    />
  );
}
