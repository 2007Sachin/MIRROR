"use client";

import { ArrowRight, GoogleLogo } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { getSupabaseBrowserClient, isSupabaseConfigured } from "@/lib/supabase";

type Mode = "login" | "signup";

function friendlyAuthError(code?: string) {
  switch (code) {
    case "invalid_credentials":
    case "email_not_confirmed":
      return "The email or password is incorrect, or the email is not confirmed.";
    case "user_already_exists":
      return "An account already exists for this email. Try signing in instead.";
    case "weak_password":
      return "Choose a stronger password with at least eight characters.";
    case "over_email_send_rate_limit":
      return "Too many attempts. Wait a few minutes and try again.";
    case "signup_disabled":
      return "New account creation is temporarily unavailable.";
    default:
      return "We could not complete authentication. Check your details and try again.";
  }
}

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [busy, setBusy] = useState(false);
  const reason = searchParams.get("reason");
  const [error, setError] = useState(
    searchParams.get("error") === "oauth"
      ? "Google sign-in could not be completed. Please try again."
      : reason === "configuration"
        ? "Authentication is not configured for this environment."
        : reason === "network"
          ? "Mirror could not reach the authentication service. Check your connection and try again."
      : reason === "session_expired"
        ? "Your session is no longer active. Please sign in again."
        : "",
  );
  const [notice, setNotice] = useState("");
  const configured = isSupabaseConfigured();
  const googleEnabled = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED === "true";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!configured) {
      setError("Authentication is not configured for this environment.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");

    try {
      const client = getSupabaseBrowserClient();
      const result = mode === "login"
        ? await client.auth.signInWithPassword({ email, password })
        : await client.auth.signUp({
            email,
            password,
            options: { data: { full_name: String(form.get("full_name") ?? "").trim() } },
          });

      if (result.error) {
        setError(friendlyAuthError(result.error.code));
        return;
      }
      if (mode === "signup" && !result.data.session) {
        setNotice("Check your email to confirm your account, then return here to sign in.");
        return;
      }
      router.replace("/app");
      router.refresh();
    } catch {
      setError("Mirror could not reach the authentication service. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  async function signInWithGoogle() {
    if (!configured) return setError("Authentication is not configured for this environment.");
    setBusy(true);
    setError("");
    try {
      const { error: oauthError } = await getSupabaseBrowserClient().auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: `${window.location.origin}/auth/callback?next=/app` },
      });
      if (oauthError) setError(friendlyAuthError(oauthError.code));
    } catch {
      setError("Mirror could not reach Google sign-in. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "login";
  return (
    <main className="shell py-14 sm:py-20">
      <div className="mx-auto max-w-md">
        <p className="text-sm text-[var(--silver)]">Private candidate access</p>
        <h1 className="display mt-4 text-4xl font-semibold tracking-[-0.05em]">
          {isLogin ? "Sign in to Mirror" : "Create your account"}
        </h1>
        <form onSubmit={submit} className="mt-10 space-y-6 border-t hairline pt-7">
          {!isLogin && (
            <label className="block">
              <span className="mb-2 block text-sm font-semibold">Full name</span>
              <input className="field" name="full_name" required maxLength={120} autoComplete="name" disabled={busy} />
            </label>
          )}
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Email</span>
            <input className="field" name="email" type="email" required autoComplete="email" disabled={busy} />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Password</span>
            <input className="field" name="password" type="password" required minLength={8} autoComplete={isLogin ? "current-password" : "new-password"} disabled={busy} />
          </label>
          {error && <p role="alert" className="border-l-2 border-red-400 pl-3 text-sm text-red-200">{error}</p>}
          {notice && <p role="status" className="border-l-2 border-[var(--pulse)] pl-3 text-sm text-[var(--paper)]">{notice}</p>}
          <button type="submit" className="button-primary w-full" disabled={busy || !configured}>
            {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"} {!busy && <ArrowRight size={18} />}
          </button>
        </form>
        {googleEnabled && (
          <button type="button" className="button-secondary mt-3 w-full" onClick={signInWithGoogle} disabled={busy || !configured}>
            <GoogleLogo size={18} /> Continue with Google
          </button>
        )}
        <p className="mt-6 text-sm text-[var(--silver)]">
          {isLogin ? "New to Mirror? " : "Already have an account? "}
          <Link className="text-[var(--paper)] underline underline-offset-4" href={isLogin ? "/signup" : "/login"}>
            {isLogin ? "Create an account" : "Sign in"}
          </Link>
        </p>
        {!configured && <p className="mt-6 text-xs leading-5 text-[var(--silver)]">Set the public Supabase URL and publishable/anonymous key to enable authentication.</p>}
      </div>
    </main>
  );
}

