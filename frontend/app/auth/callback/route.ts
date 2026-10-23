// frontend/app/auth/callback/route.ts
// ---------------------------------------------------------------
// Supabase sends the user back here after "Continue with Google" or
// after they click the sign-in link in their email. The URL holds a
// one-time ?code=... that we exchange for a real session cookie.
//
// WHAT CHANGED vs your version:
//  1. `next` is now checked with safeNext(). Before, a link like
//     /auth/callback?code=...&next=@evil.com became the redirect target
//     "https://yoursite@evil.com", which the browser treats as the
//     website evil.com (an "open redirect"). safeNext only allows
//     paths on your own site.
//  2. If Google reports a problem (user pressed Cancel) we show a
//     friendly message instead of the generic one.
// ---------------------------------------------------------------
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { safeNext } from "@/lib/auth/safe-redirect";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = safeNext(searchParams.get("next"));

  // The provider itself reported an error (e.g. user cancelled on Google).
  if (searchParams.get("error")) {
    return NextResponse.redirect(`${origin}/login?error=access_denied`);
  }

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  // Code missing, expired or already used. A common cause: the email
  // link was opened in a different browser than the one that asked for it.
  return NextResponse.redirect(`${origin}/login?error=auth`);
}
