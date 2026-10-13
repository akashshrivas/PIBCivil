"use client";

import { useEffect, useState } from "react";

// Hamburger button shown only on phones/tablets (the CSS hides it on desktop).
// Tapping it slides the sidebar in from the left, so "Dark mode" and "Account"
// are reachable on mobile.
export default function MobileMenuButton() {
  // Is the mobile menu open?
  const [open, setOpen] = useState(false);

  // Whenever "open" changes, add or remove the "sidebar-open" class on <body>.
  // globals.css uses that class to slide the sidebar in and out.
  useEffect(() => {
    document.body.classList.toggle("sidebar-open", open);
    // Cleanup: make sure the class is removed if this component goes away.
    return () => document.body.classList.remove("sidebar-open");
  }, [open]);

  // Extra ways to close the menu.
  useEffect(() => {
    // Close when a menu link (Home, Saved, ...) is tapped.
    function onClick(e: MouseEvent) {
      if ((e.target as HTMLElement).closest(".sidebar-link")) setOpen(false);
    }
    // Close when Escape is pressed.
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    // Close if the window grows to desktop size (so the class can't get stuck).
    function onResize() {
      if (window.innerWidth > 900) setOpen(false);
    }
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", onResize);
    // Cleanup: remove all three listeners.
    return () => {
      document.removeEventListener("click", onClick);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <>
      <button
        type="button"
        className="mobile-menu-btn"
        onClick={() => setOpen((v) => !v)} // flip open/closed
        aria-label="Open menu"
        aria-expanded={open}
      >
        {/* Hamburger icon: three horizontal lines */}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      {/* Dark overlay: only visible when the menu is open (see globals.css). */}
      <div className="sidebar-backdrop" onClick={() => setOpen(false)} />
    </>
  );
}
