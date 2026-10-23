// frontend/proxy.ts
// ---------------------------------------------------------------
// Runs on every page request (Next.js 16 calls this file "proxy").
//
// WHAT CHANGED vs your version:
//  - Keeps your session-refresh logic exactly as it was.
//  - NEW: pages listed in PROTECTED_PREFIXES send logged-out users to
//    /login and bring them back afterwards.
//  - NEW: a logged-in user who opens /login is sent onward.
//
// Reminder: this is a convenience layer. Anything that returns
// private data (API routes, server actions, database tables) must
// ALSO check the user itself, and tables need Row Level Security.
// ---------------------------------------------------------------
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { safeNext } from "@/lib/auth/safe-redirect";

// Pages that need a logged-in user.
const PROTECTED_PREFIXES: string[] = ["/saved", "/auth/update-password"];

function isProtected(pathname: string) {
  return PROTECTED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
}

export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // getUser() asks Supabase to verify the session (and refreshes the
  // token when needed). We now keep the result instead of ignoring it.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname, search } = request.nextUrl;

  // Redirect while keeping any freshly refreshed cookies.
  const redirectTo = (path: string) => {
    const redirect = NextResponse.redirect(new URL(path, request.url));
    response.cookies.getAll().forEach((c) => redirect.cookies.set(c));
    return redirect;
  };

  // Logged out + protected page -> login, then come back here.
  if (!user && isProtected(pathname)) {
    return redirectTo(`/login?next=${encodeURIComponent(pathname + search)}`);
  }

  // Already logged in + opening /login -> nothing to do there.
  if (user && pathname === "/login") {
    return redirectTo(safeNext(request.nextUrl.searchParams.get("next")));
  }

  return response;
}

export const config = {
  matcher: [
    // Run on everything except static assets and Next's internals.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
