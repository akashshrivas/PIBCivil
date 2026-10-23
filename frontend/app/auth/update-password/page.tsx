"use client";

// frontend/app/auth/update-password/page.tsx
// ---------------------------------------------------------------
// Opened from the password-reset email. By the time the user lands
// here, /auth/callback has already logged them in using the reset
// link, so we just set a new password for the current user.
// (proxy.ts sends anyone who is NOT logged in to /login instead.)
// ---------------------------------------------------------------
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { createClient } from "@/lib/supabase/client";

const MIN_PASSWORD_LENGTH = 8; // keep equal to the login page / Supabase setting

export default function UpdatePasswordPage() {
  const router = useRouter();
  const [supabase] = useState(() => createClient());
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");

    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }

    setLoading(true);
    const { error } = await supabase.auth.updateUser({ password });
    if (error) {
      setError("Couldn't update the password. The link may have expired. Request a new one.");
      setLoading(false);
      return;
    }
    router.replace("/");
    router.refresh();
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">Choose a new password</h1>
        <p className="auth-subtitle">Use at least {MIN_PASSWORD_LENGTH} characters.</p>

        <form onSubmit={handleSubmit} className="auth-form">
          <label className="auth-label" htmlFor="new-password">New password</label>
          <input
            id="new-password"
            type="password"
            required
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="auth-input"
            disabled={loading}
          />
          <label className="auth-label" htmlFor="confirm-password">Confirm password</label>
          <input
            id="confirm-password"
            type="password"
            required
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="auth-input"
            disabled={loading}
          />
          <div aria-live="polite">{error && <div className="auth-error" role="alert">{error}</div>}</div>
          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? "Please wait…" : "Update password"}
          </button>
        </form>
      </div>
    </div>
  );
}
