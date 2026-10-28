"use client";

// frontend/app/login/page.tsx
// ---------------------------------------------------------------
// Real-world login + sign-up page:
//   - "Sign in" tab: email + password (+ "Forgot password?")
//   - "Sign up" tab: full name + email + password (+ terms checkbox)
//   - "Continue with Google" on both tabs
//
// Your name is saved as user metadata ("full_name"). The database
// trigger you installed copies it into profiles.display_name.
//
// Existing auth-* CSS classes are reused; a few new ones (tabs,
// labels, show/hide password) are in globals-additions.css.
// ---------------------------------------------------------------

import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { createClient } from "@/lib/supabase/client";
import { safeNext } from "@/lib/auth/safe-redirect";

// Which screen is showing.
type Mode = "signin" | "signup" | "forgot";

// Keep this equal to "Minimum password length" in Supabase
// (Authentication > Sign In / Providers > Email).
const MIN_PASSWORD_LENGTH = 8;

// Seconds to wait before another email can be requested.
const EMAIL_COOLDOWN_SECONDS = 60;

// Turn a Supabase error into text that is safe to show.
// Messages are deliberately generic so they never reveal
// whether a given email address has an account.
function friendlyError(error: { code?: string; status?: number }): string {
  if (
    error.status === 429 ||
    error.code === "over_request_rate_limit" ||
    error.code === "over_email_send_rate_limit"
  ) {
    return "Too many attempts. Please wait a few minutes and try again.";
  }
  if (error.code === "invalid_credentials") {
    return "Incorrect email or password.";
  }
  if (error.code === "email_not_confirmed") {
    return "Please confirm your email first. Check your inbox for the link.";
  }
  if (error.code === "weak_password") {
    return `Choose a stronger password (at least ${MIN_PASSWORD_LENGTH} characters).`;
  }
  return "Something went wrong. Please check your details and try again.";
}

function AuthForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [supabase] = useState(() => createClient());

  // Page to open after login, e.g. /login?next=/saved (always a safe local path).
  const next = safeNext(searchParams.get("next"));

  // Message for the ?error=... codes set by /auth/callback.
  const urlError = searchParams.get("error");
  const urlErrorMessage =
    urlError === "access_denied"
      ? "Sign-in was cancelled. Please try again."
      : urlError
      ? "That link didn't work or has expired. Please try again."
      : "";

  const [mode, setMode] = useState<Mode>("signin");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [accepted, setAccepted] = useState(false); // terms checkbox (sign up)
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(urlErrorMessage);
  const [notice, setNotice] = useState("");
  // Shown after a "please confirm your email" error so the user can resend it.
  const [canResend, setCanResend] = useState(false);
  // Seconds left before another email may be requested (0 = allowed).
  const [cooldown, setCooldown] = useState(0);

  // Count the cooldown down by one every second.
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  // Where Supabase sends the user after Google / email links.
  // The URL must be listed in Supabase > Authentication > URL Configuration.
  function callbackUrl(nextPath: string) {
    return `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`;
  }

  // Switch screens; clear messages and the password field.
  function changeMode(newMode: Mode) {
    setMode(newMode);
    setError("");
    setNotice("");
    setCanResend(false);
    setPassword("");
    setShowPassword(false);
  }

  async function handleGoogle() {
    setError("");
    setLoading(true);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: callbackUrl(next),
        queryParams: { prompt: "select_account" }, // always show the account chooser
      },
    });
    // On success the browser leaves for Google, so only errors reach here.
    if (error) {
      setError("Couldn't start Google sign-in. Please try again.");
      setLoading(false);
    }
  }

  async function handleResendConfirmation() {
    setError("");
    setLoading(true);
    const { error } = await supabase.auth.resend({
      type: "signup",
      email: email.trim().toLowerCase(),
      options: { emailRedirectTo: callbackUrl(next) },
    });
    setLoading(false);
    if (error) {
      setError(friendlyError(error));
      return;
    }
    setNotice("Confirmation email sent. Check your inbox.");
    setCooldown(EMAIL_COOLDOWN_SECONDS);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); // stop the browser reloading the page
    setError("");
    setNotice("");
    setCanResend(false);

    const cleanEmail = email.trim().toLowerCase();
    const cleanName = fullName.trim();

    // Quick checks before calling the server.
    if (mode === "signup") {
      if (cleanName.length < 2) {
        setError("Please enter your full name.");
        return;
      }
      if (password.length < MIN_PASSWORD_LENGTH) {
        setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
        return;
      }
      if (!accepted) {
        setError("Please accept the Terms and Privacy Policy to continue.");
        return;
      }
    }

    setLoading(true);

    // ---------- Sign in ----------
    if (mode === "signin") {
      const { error } = await supabase.auth.signInWithPassword({
        email: cleanEmail,
        password,
      });
      if (error) {
        setError(friendlyError(error));
        setCanResend(error.code === "email_not_confirmed");
        setLoading(false);
        return;
      }
      router.replace(next); // go where the user was heading
      router.refresh(); // re-run server components so they see the login
      return;
    }

    // ---------- Sign up ----------
    if (mode === "signup") {
      const { data, error } = await supabase.auth.signUp({
        email: cleanEmail,
        password,
        options: {
          data: { full_name: cleanName }, // copied into profiles.display_name by the trigger
          emailRedirectTo: callbackUrl(next),
        },
      });
      if (error) {
        setError(friendlyError(error));
        setLoading(false);
        return;
      }
      // If "Confirm email" is OFF in Supabase we get a session straight away.
      // (Keep it ON in production.)
      if (data.session) {
        router.replace(next);
        router.refresh();
        return;
      }
      // Same message whether or not the email already exists,
      // so nobody can discover who has an account.
      setNotice("Almost there! Check your email for a link to confirm your account.");
      setCooldown(EMAIL_COOLDOWN_SECONDS);
      setLoading(false);
      return;
    }

    // ---------- Forgot password ----------
    await supabase.auth.resetPasswordForEmail(cleanEmail, {
      redirectTo: callbackUrl("/auth/update-password"),
    });
    // Always the same message, even if the email is not registered.
    setNotice("If an account exists for that email, a reset link is on its way.");
    setCooldown(EMAIL_COOLDOWN_SECONDS);
    setLoading(false);
  }

  const title =
    mode === "signin"
      ? "Welcome back"
      : mode === "signup"
      ? "Create your account"
      : "Reset your password";

  const subtitle =
    mode === "signin"
      ? "Sign in to save articles and pick up where you left off."
      : mode === "signup"
      ? "Save articles and keep them across devices."
      : "Enter your email and we'll send you a reset link.";

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <Image src="/logo.png" alt="UPSCByte logo" width={36} height={36} className="brand-logo" priority />
          <span>UPSCByte</span>
        </div>

        {/* Sign in / Sign up tabs (hidden on the forgot-password screen) */}
        {mode !== "forgot" && (
          <div className="auth-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "signin"}
              className={`auth-tab${mode === "signin" ? " active" : ""}`}
              onClick={() => changeMode("signin")}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "signup"}
              className={`auth-tab${mode === "signup" ? " active" : ""}`}
              onClick={() => changeMode("signup")}
            >
              Sign up
            </button>
          </div>
        )}

        <h1 className="auth-title">{title}</h1>
        <p className="auth-subtitle">{subtitle}</p>

        {/* Google button (not shown while resetting a password) */}
        {mode !== "forgot" && (
          <>
            <button
              type="button"
              className="auth-button auth-button-google"
              onClick={handleGoogle}
              disabled={loading}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="#4285F4" d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.47a5.53 5.53 0 0 1-2.4 3.63v3h3.89c2.27-2.09 3.58-5.17 3.58-8.82z" />
                <path fill="#34A853" d="M12 24c3.24 0 5.96-1.07 7.95-2.91l-3.89-3c-1.08.72-2.46 1.15-4.06 1.15-3.13 0-5.78-2.11-6.72-4.95H1.27v3.11A12 12 0 0 0 12 24z" />
                <path fill="#FBBC05" d="M5.28 14.29A7.2 7.2 0 0 1 4.9 12c0-.8.14-1.57.38-2.29V6.6H1.27A12 12 0 0 0 0 12c0 1.93.46 3.76 1.27 5.4z" />
                <path fill="#EA4335" d="M12 4.77c1.76 0 3.34.6 4.58 1.79l3.44-3.44C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.69 1.27 6.6l4.01 3.11C6.22 6.88 8.87 4.77 12 4.77z" />
              </svg>
              {mode === "signup" ? "Sign up with Google" : "Continue with Google"}
            </button>

            <div className="auth-divider">
              <span>or use email</span>
            </div>
          </>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          {/* Full name: sign up only */}
          {mode === "signup" && (
            <>
              <label className="auth-label" htmlFor="auth-name">
                Full name
              </label>
              <input
                id="auth-name"
                type="text"
                required
                maxLength={80}
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your name"
                className="auth-input"
                disabled={loading}
              />
            </>
          )}

          <label className="auth-label" htmlFor="auth-email">
            Email
          </label>
          <input
            id="auth-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="auth-input"
            disabled={loading}
          />

          {/* Password: not needed on the forgot-password screen */}
          {mode !== "forgot" && (
            <>
              <label className="auth-label" htmlFor="auth-password">
                Password
              </label>
              <div className="auth-pw-wrap">
                <input
                  id="auth-password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={mode === "signup" ? MIN_PASSWORD_LENGTH : undefined}
                  // Helps password managers: "current-password" when signing in,
                  // "new-password" when creating one.
                  autoComplete={mode === "signin" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "signup" ? `At least ${MIN_PASSWORD_LENGTH} characters` : "Your password"}
                  className="auth-input"
                  disabled={loading}
                />
                <button
                  type="button"
                  className="auth-pw-toggle"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </>
          )}

          {mode === "signin" && (
            <button
              type="button"
              className="auth-link-button auth-forgot"
              onClick={() => changeMode("forgot")}
            >
              Forgot password?
            </button>
          )}

          {/* Consent: sign up only */}
          {mode === "signup" && (
            <label className="auth-consent">
              <input
                type="checkbox"
                checked={accepted}
                onChange={(e) => setAccepted(e.target.checked)}
                disabled={loading}
              />
              <span>
                I agree to the <Link href="/terms">Terms</Link> and{" "}
                <Link href="/privacy">Privacy Policy</Link>.
              </span>
            </label>
          )}

          {/* aria-live makes screen readers announce messages as they appear */}
          <div aria-live="polite">
            {error && <div className="auth-error" role="alert">{error}</div>}
            {notice && <div className="auth-success" role="status">{notice}</div>}
          </div>

          {/* "Resend" appears after sign-up, or after a "please confirm" error */}
          {(canResend || (mode === "signup" && notice)) && (
            <button
              type="button"
              className="auth-link-button"
              onClick={handleResendConfirmation}
              disabled={cooldown > 0 || loading}
            >
              {cooldown > 0 ? `Resend email in ${cooldown}s` : "Resend confirmation email"}
            </button>
          )}

          <button type="submit" className="auth-button" disabled={loading || (mode !== "signin" && cooldown > 0 && !!notice)}>
            {loading
              ? "Please wait…"
              : mode === "signin"
              ? "Sign in"
              : mode === "signup"
              ? "Create account"
              : "Send reset link"}
          </button>
        </form>

        {mode === "forgot" && (
          <button
            type="button"
            className="auth-link-button"
            style={{ marginTop: 16 }}
            onClick={() => changeMode("signin")}
          >
            Back to sign in
          </button>
        )}

        <Link href="/" className="auth-guest-link">
          Continue as guest
        </Link>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <AuthForm />
    </Suspense>
  );
}
