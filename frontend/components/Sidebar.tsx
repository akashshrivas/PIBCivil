import Link from "next/link";
import DarkModeSwitch from "./DarkModeSwitch";
import SignOutButton from "./SignOutButton";
import { createClient } from "@/lib/supabase/server";

// Saved / Ministries / Calendar are placeholders for now -- Saved needs
// real auth (not built yet), Ministries/Calendar are future views on
// top of endpoints that already exist (ministry filter, date filter).
const LINKS = [
  {
    label: "Home",
    href: "/",
    active: true,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        <polyline points="9 22 9 12 15 12 15 22" />
      </svg>
    ),
  },
  {
    label: "Saved",
    href: "#",
    active: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  {
    label: "Ministries",
    href: "#",
    active: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
      </svg>
    ),
  },
  {
    label: "Calendar",
    href: "#",
    active: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="4" width="18" height="18" rx="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    ),
  },
];

export default async function Sidebar() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Prefer whichever identifier the user actually signed in with.
  const identity = user?.email ?? user?.phone ?? null;
  const initial = identity ? identity.charAt(0).toUpperCase() : null;

  return (
    <nav className="sidebar">
      <div className="sidebar-brand">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#6D5AE6" strokeWidth="2" aria-hidden="true">
          <path d="M3 21h18" />
          <path d="M5 21V7l7-4 7 4v14" />
          <path d="M9 9h.01M9 13h.01M9 17h.01M15 9h.01M15 13h.01M15 17h.01" />
        </svg>
        <div>
          <div className="sidebar-brand-text">PIBCivil</div>
          <div className="sidebar-brand-tag">Government updates, simplified.</div>
        </div>
      </div>

      <div className="sidebar-links">
        {LINKS.map((link) => (
          <a
            key={link.label}
            href={link.href}
            className={`sidebar-link${link.active ? " active" : ""}`}
          >
            {link.icon}
            {link.label}
          </a>
        ))}
      </div>

      <div className="sidebar-bottom">
        <DarkModeSwitch />
        {user ? (
          <div className="sidebar-account">
            <span className="avatar avatar-sm" aria-hidden="true">
              {initial}
            </span>
            <span className="sidebar-account-name" title={identity ?? undefined}>
              {identity}
            </span>
            <SignOutButton />
          </div>
        ) : (
          <Link href="/login" className="sidebar-account">
            <span className="avatar avatar-sm" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            </span>
            <span className="sidebar-account-name">Sign in</span>
          </Link>
        )}
      </div>
    </nav>
  );
}
