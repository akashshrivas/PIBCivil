// lib/auth/safe-redirect.ts
// ---------------------------------------------------------------
// After login we send the user to a "next" page taken from the URL
// (e.g. /login?next=/saved). If we trusted it blindly, an attacker
// could craft /login?next=https://evil.com and bounce users to a
// fake site after they log in (an "open redirect").
// This function only accepts paths that stay on OUR site.
// ---------------------------------------------------------------
export function safeNext(
  next: string | null | undefined,
  fallback = "/"
): string {
  if (!next) return fallback;
  // Must be a path on our own site, like "/saved".
  if (!next.startsWith("/")) return fallback;
  // "//evil.com" and "/\evil.com" are treated as other websites.
  if (next.startsWith("//") || next.startsWith("/\\")) return fallback;
  // Reject control characters (newlines, etc.).
  if (/[\x00-\x1f]/.test(next)) return fallback;
  return next;
}
