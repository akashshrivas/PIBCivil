"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { createClient } from "@/lib/supabase/client";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const supabase = createClient();

  const [googleLoading, setGoogleLoading] = useState(false);

  const [phone, setPhone] = useState("");
  const [phoneOtp, setPhoneOtp] = useState("");
  const [phoneStep, setPhoneStep] = useState<"input" | "otp">("input");
  const [phoneLoading, setPhoneLoading] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [emailSent, setEmailSent] = useState(false);
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);

  const oauthErrored = searchParams.get("error") === "auth";

  async function handleGoogle() {
    setGoogleLoading(true);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    // On success the browser navigates away immediately; only an error
    // path actually reaches this line.
    if (error) {
      setGoogleLoading(false);
    }
  }

  async function handlePhoneSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPhoneError(null);
    setPhoneLoading(true);
    const { error } = await supabase.auth.signInWithOtp({ phone });
    setPhoneLoading(false);
    if (error) {
      setPhoneError(error.message);
    } else {
      setPhoneStep("otp");
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault();
    setPhoneError(null);
    setPhoneLoading(true);
    const { error } = await supabase.auth.verifyOtp({ phone, token: phoneOtp, type: "sms" });
    setPhoneLoading(false);
    if (error) {
      setPhoneError(error.message);
    } else {
      router.push("/");
      router.refresh();
    }
  }

  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault();
    setEmailError(null);
    setEmailLoading(true);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setEmailLoading(false);
    if (error) {
      setEmailError(error.message);
    } else {
      setEmailSent(true);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#6D5AE6" strokeWidth="2" aria-hidden="true">
            <path d="M3 21h18" />
            <path d="M5 21V7l7-4 7 4v14" />
            <path d="M9 9h.01M9 13h.01M9 17h.01M15 9h.01M15 13h.01M15 17h.01" />
          </svg>
          <span>PIBCivil</span>
        </div>

        <h1 className="auth-title">Sign in</h1>
        <p className="auth-subtitle">Save articles and pick up where you left off.</p>

        {oauthErrored && (
          <div className="auth-error" role="alert">
            That sign-in link didn&apos;t work. Please try again.
          </div>
        )}

        <button
          type="button"
          className="auth-button auth-button-google"
          onClick={handleGoogle}
          disabled={googleLoading}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="#4285F4" d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.47a5.53 5.53 0 0 1-2.4 3.63v3h3.89c2.27-2.09 3.58-5.17 3.58-8.82z" />
            <path fill="#34A853" d="M12 24c3.24 0 5.96-1.07 7.95-2.91l-3.89-3c-1.08.72-2.46 1.15-4.06 1.15-3.13 0-5.78-2.11-6.72-4.95H1.27v3.11A12 12 0 0 0 12 24z" />
            <path fill="#FBBC05" d="M5.28 14.29A7.2 7.2 0 0 1 4.9 12c0-.8.14-1.57.38-2.29V6.6H1.27A12 12 0 0 0 0 12c0 1.93.46 3.76 1.27 5.4z" />
            <path fill="#EA4335" d="M12 4.77c1.76 0 3.34.6 4.58 1.79l3.44-3.44C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.69 1.27 6.6l4.01 3.11C6.22 6.88 8.87 4.77 12 4.77z" />
          </svg>
          {googleLoading ? "Redirecting…" : "Continue with Google"}
        </button>

        <div className="auth-divider">
          <span>or</span>
        </div>

        {phoneStep === "input" ? (
          <form onSubmit={handlePhoneSubmit} className="auth-form">
            <input
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="Phone number, e.g. +91 98765 43210"
              className="auth-input"
              aria-label="Phone number"
            />
            <button type="submit" className="auth-button" disabled={phoneLoading}>
              {phoneLoading ? "Sending code…" : "Continue with phone"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp} className="auth-form">
            <p className="auth-hint">Enter the code sent to {phone}</p>
            <input
              type="text"
              inputMode="numeric"
              required
              value={phoneOtp}
              onChange={(e) => setPhoneOtp(e.target.value)}
              placeholder="6-digit code"
              className="auth-input"
              aria-label="Verification code"
            />
            <button type="submit" className="auth-button" disabled={phoneLoading}>
              {phoneLoading ? "Verifying…" : "Verify and sign in"}
            </button>
            <button
              type="button"
              className="auth-link-button"
              onClick={() => {
                setPhoneStep("input");
                setPhoneError(null);
              }}
            >
              Use a different number
            </button>
          </form>
        )}
        {phoneError && <div className="auth-error">{phoneError}</div>}

        <div className="auth-divider">
          <span>or</span>
        </div>

        {emailSent ? (
          <div className="auth-success">
            Check <strong>{email}</strong> for a sign-in link.
          </div>
        ) : (
          <form onSubmit={handleEmailSubmit} className="auth-form">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email address"
              className="auth-input"
              aria-label="Email address"
            />
            <button type="submit" className="auth-button" disabled={emailLoading}>
              {emailLoading ? "Sending link…" : "Continue with email"}
            </button>
          </form>
        )}
        {emailError && <div className="auth-error">{emailError}</div>}

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
      <LoginForm />
    </Suspense>
  );
}
