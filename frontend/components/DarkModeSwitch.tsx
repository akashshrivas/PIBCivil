"use client";

import { useEffect, useState } from "react";

export default function DarkModeSwitch() {
  // Starts null so server/client first render match (no hydration
  // mismatch) -- real value is read from localStorage after mount.
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem("theme");
    const initial = stored === "dark" ? "dark" : "light";
    setTheme(initial);
    document.documentElement.setAttribute("data-theme", initial);
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    window.localStorage.setItem("theme", next);
  }

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      className="sidebar-darkmode"
      aria-pressed={isDark}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
      </svg>
      <span>Dark mode</span>
      <span className={`switch-track${isDark ? " on" : ""}`} aria-hidden="true">
        <span className="switch-thumb" />
      </span>
    </button>
  );
}
