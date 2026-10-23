"use client";

// frontend/components/BookmarkButton.tsx
// ---------------------------------------------------------------
// The bookmark icon on each article card.
//   - Logged out: clicking sends the user to /login, then brings
//     them back to this page afterwards.
//   - Logged in: clicking saves / un-saves the article instantly
//     ("optimistic update"), and undoes it if the database says no.
//
// Data lives in your `bookmarks` table. Your RLS policy
// ("own bookmarks") guarantees a user can only touch their own rows,
// even if someone edits this code in their browser.
// ---------------------------------------------------------------

import { useRouter } from "next/navigation";
import { useEffect, useState, type MouseEvent } from "react";
import { createClient } from "@/lib/supabase/client";

interface BookmarkButtonProps {
  articleId: string;
  initialSaved: boolean; // was it already saved when the page loaded?
  userId: string | null; // null = not logged in
}

export default function BookmarkButton({
  articleId,
  initialSaved,
  userId,
}: BookmarkButtonProps) {
  const router = useRouter();
  const [supabase] = useState(() => createClient());
  const [saved, setSaved] = useState(initialSaved);
  const [busy, setBusy] = useState(false); // blocks double-clicks mid-request

  // If the server sends a fresh value (after navigation), follow it.
  useEffect(() => {
    setSaved(initialSaved);
  }, [initialSaved]);

  async function handleClick(e: MouseEvent<HTMLButtonElement>) {
    // The button sits inside the card's <Link>. Without these two lines,
    // clicking the bookmark would ALSO open the article.
    e.preventDefault();
    e.stopPropagation();

    // Not logged in: go to login and return to this exact page afterwards.
    if (!userId) {
      const here = window.location.pathname + window.location.search;
      router.push(`/login?next=${encodeURIComponent(here)}`);
      return;
    }
    if (busy) return;

    const wantSaved = !saved;
    setSaved(wantSaved); // update the icon immediately
    setBusy(true);

    const { error } = wantSaved
      ? await supabase
          .from("bookmarks")
          .insert({ user_id: userId, article_id: articleId })
      : await supabase
          .from("bookmarks")
          .delete()
          .eq("user_id", userId)
          .eq("article_id", articleId);

    // 23505 = "already exists": it was saved already, which is the
    // result we wanted anyway, so it is not a real failure.
    if (error && error.code !== "23505") {
      setSaved(!wantSaved); // undo the optimistic change
    } else if (window.location.pathname === "/saved") {
      // On the Saved page, refresh so an un-saved article disappears.
      router.refresh();
    }
    setBusy(false);
  }

  return (
    <button
      type="button"
      className={`article-save${saved ? " saved" : ""}`}
      onClick={handleClick}
      aria-pressed={saved}
      aria-label={saved ? "Remove from saved" : "Save article"}
      title={saved ? "Remove from saved" : "Save article"}
    >
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill={saved ? "currentColor" : "none"} // filled when saved
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
      </svg>
    </button>
  );
}
