"use client";

import { useEffect, useRef, useState } from "react";

interface DropdownOption {
  value: string;
  label: string;
}

interface DropdownProps {
  icon: React.ReactNode;
  value: string;
  placeholder: string;
  options: DropdownOption[];
  onChange: (value: string) => void;
  /** Show a "clear selection" row at the top (default true). Set false
   * when every real option is always meaningful on its own, e.g. Sort. */
  clearable?: boolean;
}

export default function Dropdown({
  icon,
  value,
  placeholder,
  options,
  onChange,
  clearable = true,
}: DropdownProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const selectedLabel = options.find((o) => o.value === value)?.label ?? placeholder;

  return (
    <div className="dropdown" ref={containerRef}>
      <button type="button" className="filter-field" onClick={() => setOpen((v) => !v)}>
        {icon}
        <span>{selectedLabel}</span>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="dropdown-popover">
          {clearable && (
            <button
              type="button"
              className={`dropdown-option${value === "" ? " active" : ""}`}
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
            >
              {placeholder}
            </button>
          )}
          {options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`dropdown-option${value === opt.value ? " active" : ""}`}
              onClick={() => {
                onChange(opt.value);
                setOpen(false);
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
